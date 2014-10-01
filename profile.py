#!/usr/bin/env python3
from useful.run import run
from perf.perftool import stat
import atexit
from time import sleep
import os
from os import kill
from signal import SIGSTOP, SIGCONT, SIGKILL

THRESH = 10 # min CPU usage in %

def get_heavy_tasks(thr=THRESH, t=0.3):
  from psutil import process_iter
  [p.cpu_percent() for p in process_iter()]
  sleep(t)
  ## short version
  # return [p.pid for p in process_iter() if p.cpu_percent()>10]
  r = []
  for p in process_iter():
    cpu = p.cpu_percent()
    if cpu > 10:
      print("{pid:<7} {name:<12} {cpu}".format(pid=p.pid, name=p.name(), cpu=cpu))
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
  cmd = "schedtool -a %s %s" % (hex(cpu), pid)
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
    r = stat(pid=self.pid,
             events=['instructions', 'cycles'],
             time=time)
    instructions = r['instructions']
    cycles = r['cycles']
    if instructions == 0 or cycles == 0:
      return None
    return instructions / cycles
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


def generate_load():
  from subprocess import Popen
  for x in range(2):
    p = Popen("burnP6")
    atexit.register(p.kill)


#TODO: change generate_load to false
def task_profile(gen_load:int=0):
  if gen_load:
    generate_load()
  pids = get_heavy_tasks()
  tasks = [Task(pid) for pid in pids]

if __name__ == '__main__':
  print(task_profile())