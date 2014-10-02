#!/usr/bin/env python3
from useful.run import run
from perf.perftool import ipc
import atexit
from time import sleep
import os
from os import kill
from signal import SIGSTOP, SIGCONT, SIGKILL
from collections import defaultdict
from statistics import mean
from perf.numa import topology
import argparse


def get_heavy_tasks(thr, t=0.3):
  from psutil import process_iter
  [p.cpu_percent() for p in process_iter()]
  sleep(t)
  ## short version
  # return [p.pid for p in process_iter() if p.cpu_percent()>10]
  r = []
  print("topmost resource hogs:")
  for p in process_iter():
    cpu = p.cpu_percent()
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
  print("pinning %s to %s" %(pid, cpu))
  mask = 1<<cpu
  cmd = "schedtool -a %s %s" % (hex(mask), pid)
  run(cmd, sudo='root')


class Task:
  tasks =  []
  def __init__(self, pid):
    os.kill(pid, 0)  # check if pid is alive
    self.pid = pid
    self.orig_affinity =  get_affinity(pid)
    self.affinity = self.orig_affinity
    self.tasks.append(self)

  def pin(self, cpu=None):
    """ Pin task to the specific cpu.
        Pins to current cpu if none provided.
    """
    if not cpu:
      cpu = get_cur_cpu(self.pid)
    pin_task(self.pid, cpu)
    self.affinity = cpu
    return cpu

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


def get_sys_ipc(t=1.0):
  r = ipc(time=1)
  print("system IPC: {:.3}".format(r))
  return r


def generate_load(num):
  from subprocess import Popen
  for x in range(num):
    p = Popen("burnP6")
    atexit.register(p.kill)


def get_pinned_tasks(threshold):
  pids = get_heavy_tasks(threshold)
  print("pids for consideration:", pids)
  tasks = [Task(pid) for pid in pids]
  for task in tasks:
    task.pin()
  return tasks


def task_profile(task, shared, ideal, ratio, t=0.1):
  shared_ipc = task.ipc(t)
  task.exclusive()
  ideal_ipc = task.ipc(t)
  task.shared()

  shared[task].append(shared_ipc)
  ideal[task].append(ideal_ipc)
  ratio[task].append(shared_ipc / ideal_ipc)


def reduce_and_sort_by_value(d):
  for k,v in d.items():
    d[k] = mean(v)
  return sorted(d.items(), key=lambda x: -x[1])


def sys_optimize_dead_simple(tasks, repeat=1):
  shared = defaultdict(list)
  ideal  = defaultdict(list)
  ratio  = defaultdict(list)

  for i in range(repeat):
    for task in tasks:
      task_profile(task, shared, ideal, ratio)

  by_impact = reduce_and_sort_by_value(ratio)
  for (t,_), cpu in zip(by_impact, topology.no_ht):
    t.pin(cpu)
  return ratio


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  # parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  # parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-t', '--threshold', type=int, default=10,
                      help="consider only tasks consuming more CPU than this")
  args = parser.parse_args()
  print("config:", args)

  generate_load(4)
  tasks = get_pinned_tasks(args.threshold)
  sleep(2)  # warm-up

  # initial performance
  before_sys_ipc =  get_sys_ipc()

  print(sys_optimize_dead_simple(tasks))

  # after tasks were optimized
  after_sys_ipc =  get_sys_ipc()
  improvement = (after_sys_ipc - before_sys_ipc) / before_sys_ipc
  print("improvement: {:.1%}".format(improvement))