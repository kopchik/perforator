#!/usr/bin/env python3

from perf.utils import wait_idleness
from perf.numa import topology
from perf.perftool import ipc
from useful.run import run
import perf; perf.min_version((2,4))

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
  ffmpeg = "ffmpeg -i /home/sources/avatar_trailer.m2ts \
            -threads 1 -t 10 -y -strict -2 -loglevel panic \
            -acodec aac -aq 100 \
            -vcodec libx264 -preset fast -crf 22 \
            -f mp4 /dev/null",
)


def generate_load(num):
  pids = []
  for x in range(num):
    name, cmd = choice(list(basis.items()))
    p = Popen(shlex.split(cmd), stdout=DEVNULL, stderr=DEVNULL)
    atexit.register(p.kill)
    print("{:<8} {}".format(p.pid, name))
    pids.append(p.pid)
  return pids

def get_heavy_tasks(thr, t=1):
  from psutil import process_iter
  [p.cpu_percent() for p in process_iter()]
  sleep(t)
  r = []
  print("topmost resource hogs:")
  for p in process_iter():
    cpu = p.cpu_percent(None)
    if cpu > 10:
      print("{pid:<7} {name:<12} {cpu}% CPU".format(pid=p.pid, name=p.name(), cpu=cpu))
      r.append(p.pid)
  return r


def get_affinity(pid):
  cmd = "schedtool %s" % pid
  raw = run(cmd)
  rawmask = raw.rsplit(b'AFFINITY')[1]
  return int(rawmask, base=16)


def get_cur_cpu(pid):
  cmd = "ps h -p %s -o psr" % pid
  rawcpu = run(cmd)
  return int(rawcpu)


def pin_task(pid, cpu):
  cmd = "taskset -apc %s %s" % (cpu, pid)
  run(cmd, sudo='root')


class Task:
  tasks =  []
  def __init__(self, pid):
    kill(pid, 0)  # check if pid is alive
    self.pid = pid
    self.cpu = None
    self.tasks.append(self)

  def pin(self, cpu=None):
    """ Pin task to the specific cpu.
        Pins to current cpu if none provided.
    """
    if not cpu:
      cpu = get_cur_cpu(self.pid)
    if self.cpu and self.cpu == cpu:
      print("%s is still pinned to %s" % (self.pid, cpu))
      return
    pin_task(self.pid, cpu)
    if self.cpu:
      print("migrating pid %s: %s -> %s" % (self.pid, self.cpu, cpu))
    else:
      print("pinning %s to %s" %(pid, cpu))
    self.cpu = cpu

  def kill(self, sig=SIGKILL):
    kill(self.pid, sig)

  def unpin(self):
    pin_task(self.orig_affinity)

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
    return "%s(%s)" %(cls, self.pid)


def get_sys_ipc(t=3.0):
  r = ipc(time=1)
  print("system IPC: {:.3}".format(r))
  return r


def get_pinned_tasks(threshold):
  pids = get_heavy_tasks(threshold)
  print("pids for consideration:", pids)
  tasks = [Task(pid) for pid in pids]
  for task in tasks:
    task.pin()
  return tasks


def task_profile(task, shared, ideal, impact, t=0.1):
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


def get_impact(shared, ideal):
  return ideal - shared


def sys_optimize_dead_simple(tasks, repeat=3):
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
    t.pin(cpu)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  # parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  # parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-t', '--threshold', type=int, default=10,
                      help="consider only tasks consuming more CPU than this")
  args = parser.parse_args()
  print("config:", args)
  print(topology)

  wait_idleness(100, t=3)
  pids = generate_load(num=len(topology.all))
  sleep(10)  # warm-up

  tasks = []
  for pid in pids:
    task = Task(pid)
    task.pin()
    tasks.append(task)

  # initial performance
  before_sys_ipc =  get_sys_ipc()

  print(sys_optimize_dead_simple(tasks))

  # after tasks were optimized
  after_sys_ipc =  get_sys_ipc()
  improvement = (after_sys_ipc - before_sys_ipc) / before_sys_ipc
  print("improvement: {:.1%}".format(improvement))
  print("{:.3}".format(improvement), file=sys.stderr)