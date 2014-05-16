#!/usr/bin/env python3
from collections import OrderedDict, defaultdict
from itertools import permutations
from threading import Thread
from statistics import mean
from os.path import exists
from time import sleep
import argparse
import atexit
import pickle

from perf.utils import wait_idleness
from perf.config import basis, IDLENESS
from useful.small import dictzip, invoke
from useful.mystruct import Struct
from qemu import vms


THRESH = 10 # min CPU usage in %


class Setup:
  pipes = None

  def __init__(self, benchmarks):
    self.benchmarks = benchmarks
    self.pipes = []

  def __enter__(self):
    map = {}
    wait_idleness(IDLENESS*2)
    for bname, vm in zip(self.benchmarks, vms):
      #print("{} for {} {}".format(bname, vm.name, vm.pid))
      cmd = basis[bname]
      map[vm.pid] = bname
      p = vm.Popen(cmd)
      vm.bname = bname
      self.pipes.append(p)
    return map

  def __exit__(self, *args):
    for vm in vms:
      vm.unfreeze()
    for p in self.pipes:
      p.killall()


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


def generate_load():
  from subprocess import Popen
  for x in range(2):
    p = Popen("burnP6")
    atexit.register(p.kill)


def threadulator(f, params):
  '''execute routine actions in parallel'''
  threads = []
  for param in params:
    t = Thread(target=f, args=param)
    threads.append(t)
  [t.start() for t in threads]
  [t.join() for t in threads]


def unpack(tuples):
  print(tuples)
  r1, r2 = [], []
  for (v1,v2) in tuples:
    r1.append(v1)
    r2.append(v2)
  return r1,r2


def rawprofile(vms, time=1.0, freq=100, pause=0.1, num=10):
  r = defaultdict(list)
  interval = int(1/freq*1000)
  assert interval >= 1, "too high freqency, should be > 1000Hz (>100Hz recommended)"
  assert len(vms) > 1, "at least two tasks should be given"
  for _ in range(num):
    for vm in vms:
      # phase 1: measure with other task in system
      #print("shared")
      shared, _ = vm.stat(time, interval)

      sleep(pause)  # let system stabilze after defrost
      # phase 2: exclusive resource usage
      #print("exclusive")
      vm.exclusive()
      exclusive, _ = vm.stat(time, interval)
      vm.shared()

      # calculate results
      #result = mean(shared[skip:])/mean(exclusive[skip:])
      r[vm.name].append((shared,exclusive))

      #print("pause")
      sleep(pause)  # let system stabilze after defrost
  return r


def real_interference(vms, time, freq=1):
  result = OrderedDict()
  interval = int(1/freq*1000)
  for vm in vms:
    vm.freeze()

  for predator, victim in permutations(vms, 2):
    # exclusive
    victim.unfreeze()
    exclusive, _ = victim.stat(time, interval)
    # shared
    predator.unfreeze()
    shared, _ = victim.stat(time, interval)
    # tear down
    predator.freeze()
    victim.freeze()
    # save results
    key = predator.bname, victim.bname
    value = mean(shared) / mean(exclusive)
    print(key, value)
    result[key] = value

  for vm in vms:
    vm.unfreeze()
  return result


def reverse(num:int=1, time:float=1.0, pause:float=0.1, vms=None):
  assert vms, "vms is a mandatory argument"
  result = defaultdict(list)

  def measure(vm, r):
    ins, cycles = vm.stat(time)
    r[vm.bname] = ins/cycles

  for i in range(num):
    print("measure %s out of %s" % (i+1, num))
    for victim in vms:
      """victim is a VM that we are going to freeze"""
      shared, exklusiv = {}, {}
      # shared phase
      threadulator(measure, [(vm, shared) for vm in vms if vm != victim])
      # "stop victim" phase
      victim.freeze()
      threadulator(measure, [(vm, exklusiv) for vm in vms if vm != victim])
      victim.unfreeze()
      # calculate results
      for bench, pShared, pExcl in dictzip(shared, exklusiv):
        key = victim.bname, bench
        value = pShared/pExcl
        result[key].append(value)
      sleep(pause)
  return result


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  #parser.add_argument('-s', '--skip', type=int, default=0, help="number of initial samples to skip")
  parser.add_argument('-o', '--output', default=None, help="Where to put results")
  parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  parser.add_argument('-t', '--test', help="test specification")
  parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-b', '--benches', nargs='+', default="matrix wordpress blosc static".split(), help="which benchmarks to run")
  args = parser.parse_args()
  print("config:", args)

  assert not args.output or not exists(args.output), "output %s already exists" % args.output

  with Setup(args.benches):
    func, params = invoke(args.test, globals(), vms=vms)
    print("invoking", func.__name__, "with", params)
    result = func(**params)
    if args.print:
      print(result)

    if args.output:
      if args.output == 'auto':
        params.pop('vms')
        csv = ",".join('%s=%s' % (k,v) for k,v in sorted(params.items()))
        fname = 'results/%s_%s.pickle' % (func.__name__, csv)
      else:
        fname = args.output
      print("pickling to", fname)
      pickle.dump(Struct(args=args, result=result), open(fname, "wb"))
