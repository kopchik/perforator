#!/usr/bin/env python3
import pyximport; pyximport.install(pyimport = True)
from perflib import Task

from psutil import process_iter
from subprocess import Popen
from time import time, sleep
from statistics import mean
import atexit

PERIOD = 0.01
TIME = 0.1
TIMES = round(TIME/PERIOD)
THRESH = 10 # min CPU usage in %


def get_heavy_tasks(thr=THRESH, t=0.3):
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


def unpack(tuples):
  r1, r2 = [], []
  for (v1,v2) in tuples:
    r1.append(v1)
    r2.append(v2)
  return r1,r2


def profile(tasks):
  assert len(tasks) > 1, "at least two tasks should be given"
  while True:
    for t in tasks:
      # phase 1: measure with other tools
      shared, _ = unpack(t.measurex(PERIOD, TIMES))
      t.freeze(tasks)
      # phase 2: exclusive resource usage
      exclusive, _ = unpack(t.measurex(PERIOD, TIMES))
      t.defrost(tasks)
      print(mean(shared)/mean(exclusive))
      sleep(1)


def prepare():
  for x in range(2):
    p = Popen("burnP6")
    atexit.register(p.kill)


if __name__ == '__main__':
  prepare()
  pids = get_heavy_tasks()
  tasks = [Task(p) for p in pids]
  profile(tasks)