#!/usr/bin/env python3
from time import time, sleep
from statistics import mean
import argparse
import atexit

from perf.utils import wait_idleness
from perf.config import basis, IDLENESS
from qemu import vms

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


def unpack(tuples):
  print(tuples)
  r1, r2 = [], []
  for (v1,v2) in tuples:
    r1.append(v1)
    r2.append(v2)
  return r1,r2


from collections import defaultdict
def profile(vms, time, interval, pause=0.1, repeat=1):
  r = defaultdict(list)
  assert len(vms) > 1, "at least two tasks should be given"
  for _ in range(repeat):
    for vm in vms:
      # phase 1: measure with other tools
      print("shared")
      shared, _ = vm.stat(time, interval)

      # phase 2: exclusive resource usage
      print("exclusive")
      vm.exclusive()
      exclusive, _ = vm.stat(time, interval)
      vm.shared()

      # calculate results
      result = mean(shared)/mean(exclusive)
      r[vm].append(result)
      print("pause")
      sleep(pause)  # let system stabilze after defrost
  return r


def generate_load():
  from subprocess import Popen
  for x in range(2):
    p = Popen("burnP6")
    atexit.register(p.kill)




class Zhest:
  pipes = None

  def __init__(self, benchmarks):
    self.pipes = []
    self.benchmarks = benchmarks

  def __enter__(self):
    map = {}
    wait_idleness(IDLENESS*2)
    for bname, vm in zip(self.benchmarks, vms):
      print("{} for {} {}".format(bname, vm.name, vm.pid))
      cmd = basis[bname]
      map[vm.pid] = bname
      p = vm.Popen(cmd)
      self.pipes.append(p)
    return map

  def __exit__(self, *args):
    for p in self.pipes:
      p.killall()
    vms[0].shared()


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  parser.add_argument('-t', '--time', type=float, default=0.1, help="measurement time (in _seconds_!)")
  parser.add_argument('-p', '--pause', type=float, default=0.1, help="pause between measurements (in _seconds_!)")
  parser.add_argument('-i', '--interval', type=int, default=100, help="interval between measurements in seconds")
  parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  args = parser.parse_args()
  print("config:", args)

  #benchmarks = "matrix wordpress blosc static sdag sdagp ffmpeg pgbench".split()
  benchmarks = "matrix wordpress blosc static".split()
  with Zhest(benchmarks) as map:
    print(profile(vms, args.time, args.interval, pause=args.pause))

  #prepare()
  #pids = get_heavy_tasks()
  #tasks = [Task(p) for p in pids]
  #profile(tasks, args.interval, args.num_samples)
