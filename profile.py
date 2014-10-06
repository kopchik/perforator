#!/usr/bin/env python3

from perf.utils import wait_idleness
from perf.numa import topology
from perf.perftool import ipc, stat
from useful.run import run
import perf; perf.min_version((2,8))

from signal import SIGSTOP, SIGCONT, SIGKILL
from collections import defaultdict
from statistics import mean
from subprocess import Popen, DEVNULL
from random import choice
from time import sleep
from os import kill

import argparse
import atexit
import shlex
import sys

BENCHES = "/home/sources/perftest/benches/"
basis = dict(
  # INIT DB: sudo -u postgres pgbench -i
  # pgbench = "sudo -u postgres pgbench -c 20 -s 10 -T 100000",
  # static  = "siege -c 100 -t 666h http://localhost/big_static_file",  # TODO: too CPU consuming,
  # wordpress = "siege -c 100 -t 666h http://localhost/",
  # matrix = "/home/sources/perftest/benches/matrix.py -s 1024 -r 1000",
  matrix = BENCHES + "matrix 2048",
  # sdag   = BENCHES + "test_SDAG/test_sdag -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat",
  # sdagp  = BENCHES + "test_SDAG/test_sdag+ -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat",
  blosc  = BENCHES + "pyblosc.py -r 10000000",
  burnP6 = "burnP6",
  ffmpeg = "ffmpeg -i /home/sources/ToS-4k-1920.mov" \
           " -threads 1 -y -strict -2 -loglevel panic" \
           " -acodec aac -aq 100" \
           " -vcodec libx264 -preset fast -crf 22" \
           " -f mp4 /dev/null",
)
for k,v in basis.items(): print("{:<10} {}".format(k,v))

class cfg:
  sys_ipc_time = 3
  task_profile_time = 0.1
  sys_optimize_samples = 10
  warmup_time = 3
  idleness = 100


def generate_load(num):
  tasks = []
  for i in range(num):
    name, cmd = choice(list(basis.items()))
    p = Popen(shlex.split(cmd), stdout=DEVNULL, stderr=DEVNULL)
    atexit.register(p.kill)
    print("{:<8} {}".format(p.pid, name))
    task = Task(p.pid, name=name)
    #task.pin([i])
    tasks.append(task)
  return tasks


def get_heavy_tasks(thr, t=1):
  from psutil import process_iter
  [p.cpu_percent() for p in process_iter()]
  sleep(t)
  r = []
  #print("topmost resource hogs:")
  for p in process_iter():
    cpu = p.cpu_percent(None)
    if cpu > 10:
      print("{pid:<7} {name:<12} {cpu}% CPU".format(pid=p.pid, name=p.name(), cpu=cpu))
      r.append(p.pid)
  return r


def get_cur_cpu(pid):
  cmd = "ps h -p %s -o psr" % pid
  rawcpu = run(cmd)
  return int(rawcpu)


def pin_task(pid, cpu):
  cmd = "taskset -apc %s %s" % (cpu, pid)
  run(cmd, sudo='root')


def get_affinity(pid):
  cmd = "schedtool %s" % pid
  raw = run(cmd)
  rawmask = raw.rsplit(b'AFFINITY')[1]
  return int(rawmask, base=16)


def set_affinity(pid, mask):
  cmd = "taskset -ap %s %s" % (mask, pid)
  run(cmd, sudo='root')


def cpus_to_mask(cpus):
  mask = 0x0
  for cpu in cpus:
    mask |= 1 << cpu
  return mask


def mask_to_cpus(mask):
  cpus = []
  i = 0
  while mask:
    if mask & 1:
      cpus.append(i)
    i += 1
    mask = mask >> 1
  return cpus


class Task:
  tasks =  []
  def __init__(self, pid, name):
    kill(pid, 0)  # check if pid is alive
    self.pid = pid
    self.cpus = ()
    self.name = name
    self.tasks.append(self)

  def pin(self, cpus):
    """ Pin task to the specific cpu.
        Pins to current cpu if none provided.
    """
    if self.cpus == cpus:
      print("%s is still pinned to %s" % (self.pid, cpus))
      return
    # if self.cpus:
    #   print("migrating pid %s: %s -> %s" % (self.pid, self.cpus, cpus))
    # else:
    #   print("pinning %s to %s" %(self.pid, cpus))
    mask = cpus_to_mask(cpus)
    self.set_affinity(mask)
    self.cpus = cpus

  def kill(self, sig=SIGKILL):
    kill(self.pid, sig)

  def set_affinity(self, mask):
    print("setting affinity to 0x{mask:X} {list}".format(mask=mask, list=mask_to_cpus(mask)))
    set_affinity(self.pid, mask)

  def ipc(self, time=0.1):
    return ipc(pid=self.pid, time=time)

  def shared(self):
    for t in self.tasks:
      if t == self:
        continue
      t.kill(SIGCONT)

  def exclusive(self):
    for t in self.tasks:
      if t == self:
        continue
      t.kill(SIGSTOP)

  def __repr__(self):
    cls = self.__class__.__name__
    return "%s(%s, %s)" %(cls, self.pid, self.name)


def get_sys_ipc(t=cfg.sys_ipc_time):
  r = ipc(time=t)
  print("system IPC: {:.3}".format(r))
  return r


def get_sys_perf(t=cfg.sys_ipc_time):
  r = stat(time=t, events=['instructions'], systemwide=True)
  m_ins = r['instructions']/t/1024/1024/1024
  print("system performance: {:.2f} giga instructions per second".format(m_ins))
  return m_ins


def get_pinned_tasks(threshold):
  pids = get_heavy_tasks(threshold)
  print("pids for consideration:", pids)
  tasks = [Task(pid) for pid in pids]
  for task in tasks:
    task.pin()
  return tasks


def task_profile(task, shared, ideal, impact, t=cfg.task_profile_time):
  # shared performace
  shared_ipc = task.ipc(t)

  # ideal performance
  task.exclusive()
  ideal_ipc = task.ipc(t)
  # unfreeze system
  task.shared()
  r   = shared_ipc / ideal_ipc
  imp = ideal_ipc - shared_ipc

  shared[task].append(shared_ipc)
  ideal[task].append(ideal_ipc)
  impact[task].append(imp*r)


def sys_optimize_dead_simple1(tasks, repeat=cfg.sys_optimize_samples):
  shared = defaultdict(list)
  ideal  = defaultdict(list)
  impact = defaultdict(list)

  for i in range(repeat):
    for task in tasks:
      task_profile(task, shared, ideal, impact)

  impact = {}
  for task in tasks:
    impact[task] = mean(ideal[task])-mean(shared[task])
  by_impact = sorted(impact.items(), key=lambda x: x[1], reverse=True)
  print("by impact:", by_impact)
  for (t,_), cpu in zip(by_impact, topology.by_rank):
    t.pin([cpu])


def sys_optimize_dead_simple3(tasks, repeat=cfg.sys_optimize_samples):
  shared = defaultdict(list)
  ideal  = defaultdict(list)
  impact = defaultdict(list)

  for i in range(repeat):
    for task in tasks:
      task_profile(task, shared, ideal, impact)

  print_stat(tasks, shared, ideal)

  impact = {}
  for task in tasks:
    impact[task] = mean(ideal[task])-mean(shared[task])
  by_impact = sorted(ideal.items(), key=lambda x: x[1])
  print("by impact:", by_impact)

  task, _ = by_impact.pop(0)
  cpu1 = topology.by_rank[0]
  cpu2 = topology.ht_map[cpu1][0]
  mask = cpus_to_mask([cpu1, cpu2])
  task.pin([cpu1])
  others_mask = 0xff & (~mask & 0xFF)

  for task, _ in by_impact:
    task.set_affinity(others_mask)



def print_stat(tasks, shared, ideal):
  for task in tasks:
    s = mean(shared[task])
    i = mean(ideal[task])
    diff = i - s
    rel  = (i -s) / i
    print("{task} -- {shared:.2f}   {ideal:.2f}   {diff:.2f}   {rel:.1%}" \
        .format(task=task, shared=s, ideal=i, diff=diff, rel=rel))


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  # parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  # parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-t', '--threshold', type=int, default=10,
                      help="consider only tasks consuming more CPU than this")
  parser.add_argument('-o', '--output',
                      help="output file")
  args = parser.parse_args()
  print("config:", args)
  print(topology)

  wait_idleness(cfg.idleness, t=3)
  tasks = generate_load(num=len(topology.all))

  #warm-up
  sleep(cfg.warmup_time)

  # initial performance
  perf_before =  get_sys_perf()

  print(sys_optimize_dead_simple3(tasks))

  # after tasks were optimized
  perf_after =  get_sys_perf()
  improvement = (perf_after - perf_before) / perf_before * 100
  print("improvement: {:.1f}%".format(improvement))
  if args.output:
    print("{:.1f}".format(improvement), file=open(args.output, 'at'))
