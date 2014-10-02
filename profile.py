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


THRESH = 10 # min CPU usage in %


def get_heavy_tasks(thr=THRESH, t=0.3):
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

  def pin(self):
    cur_cpu = get_cur_cpu(self.pid)
    pin_task(self.pid, cur_cpu)
    self.affinity = cur_cpu
    return cur_cpu

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

def generate_load():
  from subprocess import Popen
  for x in range(2):
    p = Popen("burnP6")
    atexit.register(p.kill)

def get_pinned_tasks():
  pids = get_heavy_tasks()
  print("pids for consideration:", pids)
  tasks = [Task(pid) for pid in pids]
  for task in tasks:
    task.pin()
  return tasks

#TODO: change generate_load to false
def sys_optimize_deadsimple(tasks, repeat=1):
  profiles = defaultdict(list)
  for i in range(repeat):
    for task in tasks:
      ipc = task_profile(task)
      if ipc:
        profiles[task].append(ipc)

  profile = {}
  for k,v in profiles.items():
    profile[k] = mean(v)

  return profile


def task_profile(task, t=0.1):
  shared_ipc = task.ipc(t)
  task.exclusive()
  exclusive_ipc = task.ipc(t)
  task.shared()
  if not shared_ipc or not exclusive_ipc:
    return None
  return shared_ipc / exclusive_ipc


if __name__ == '__main__':
  generate_load()
  tasks = get_pinned_tasks()
  sleep(1)  # warm-up


  # initial performance
  before_sys_ipc =  get_sys_ipc()

  print(sys_optimize_deadsimple(tasks))

  # after tasks were optimized
  after_sys_ipc =  get_sys_ipc()
  improvement = (after_sys_ipc - before_sys_ipc) / before_sys_ipc
  print("improvement: {:.1%}".format(improvement))