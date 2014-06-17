#!/usr/bin/env python3
from collections import OrderedDict, defaultdict
from itertools import permutations
from threading import Thread
from statistics import mean
from socket import gethostname
from os.path import exists
from time import sleep
from math import ceil
import argparse
import atexit
import pickle

from perf.perftool import NotCountedError
from perf.utils import wait_idleness
from useful.small import dictzip, invoke
from useful.mystruct import Struct
from config import basis, VMS, IDLENESS


THRESH = 10 # min CPU usage in %


class Setup:
  pipes = None

  def __init__(self, vms, benchmarks):
    self.benchmarks = benchmarks
    self.vms = vms
    self.pipes = []
    if any([vm.start() for vm in vms]):
      print("some of vms were not started, giving it time to start")
      sleep(10)

  def __enter__(self):
    map = {}
    wait_idleness(IDLENESS*6)
    for bname, vm in zip(self.benchmarks, self.vms):
      #print("{} for {} {}".format(bname, vm.name, vm.pid))
      cmd = basis[bname]
      p = vm.Popen(cmd)
      vm.bname = bname
      self.pipes.append(p)
    print("benches warm-up for 10 seconds")
    sleep(10)
    return map

  def __exit__(self, *args):
    for vm in self.vms:
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


def reverse_isolated(num, time, pause, vms=None):
  result = defaultdict(list)
  for vm in vms:
    vm.freeze()

  for i in range(num):
    print("measure %s out of %s" % (i+1, num))
    for predator, victim in permutations(vms, 2):
      try:
        # exclusive
        victim.unfreeze()
        i, c = victim.stat(time)
        exclusive = i / c
        # shared
        predator.unfreeze()
        i, c = victim.stat(time)
        shared = i / c
        # tear down
        predator.freeze()
        victim.freeze()
        # save results
      except NotCountedError:
        print("we missed a data point")
        predator.freeze()
        victim.freeze()
        continue
      key = predator.bname, victim.bname
      result[key].append(shared / exclusive)
      sleep(pause)

  for vm in vms:
    vm.unfreeze()
  return result


def reverse_shared(num:int=1, time:float=0.1, pause:float=0.1, vms=None):
  assert vms, "vms is a mandatory argument"
  result = defaultdict(list)

  def measure(vm, r):
    ins, cycles = vm.stat(time)
    r[vm.bname] = ins / cycles

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
      try:
        for bench, pShared, pExcl in dictzip(shared, exklusiv):
          key = victim.bname, bench
          value = pShared / pExcl
          result[key].append(value)
      except KeyError:
        print("something was wrong, we lost a datapoint")
      sleep(pause)
  return result


def reverse(num:int=1, time:float=0.1, pause:float=0.1, vms=None):
  print("isolated")
  isolated = reverse_isolated(num=num, time=time, pause=pause, vms=vms)
  print("shared")
  shared = reverse_shared(num=num, time=time, pause=pause, vms=vms)
  return Struct(isolated=isolated, shared=shared)


def distribution(num:int=1,interval:float=0.1, pause:float=0.1, vms=None):
  pure = defaultdict(list)
  quasi = defaultdict(list)

  # STEP 1: purely isolated performance
  for vm in vms:
    vm.freeze()

  for i,vm in enumerate(vms):
    print("step 1: {} out of {}".format(i+1, len(vms)))
    vm.unfreeze()
    for _ in range(num):
      try:
        ipc = vm.ipcstat(interval)
        pure[vm.bname].append(ipc)
        print("saving pure to", vm.bname, ipc)
      except NotCountedError:
        pass
    vm.freeze()

  for vm in vms:
    vm.unfreeze()

  # STEP 2: quasi-isolated performance
  for i,vm in enumerate(vms):
    print("step 2: {} out of {} for {}".format(i+1, len(vms), vm.bname))
    for _ in range(num):
      sleep(pause)
      vm.exclusive()
      try:
        ipc = vm.ipcstat(interval)
        quasi[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()

  return Struct(pure=pure, quasi=quasi)


def shared(num:int=1,interval:float=0.1, pause:float=0.1, vms=None):
  result = defaultdict(list)

  for i in range(num):
    if i%10 == 0:
      print("step 1: {} out of {}".format(i+1, num))
    for vm in vms:
      try:
        ipc = vm.ipcstat(interval)
        result[vm.bname].append(ipc)
      except NotCountedError:
        pass

  return result



if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  #parser.add_argument('-s', '--skip', type=int, default=0, help="number of initial samples to skip")
  parser.add_argument('-o', '--output', default=None, help="Where to put results")
  parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  parser.add_argument('-t', '--test', help="test specification")
  parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-b', '--benches', nargs='+', default="matrix wordpress blosc static sdag sdagp pgbench ffmpeg".split(), help="which benchmarks to run")
  args = parser.parse_args()
  print("config:", args)

  assert not args.output or not exists(args.output), "output %s already exists" % args.output

  with Setup(VMS, args.benches):
    sleep(20)  # warm-up time
    func, params = invoke(args.test, globals(), vms=VMS)
    print("invoking", func.__name__, "with", params)
    result = func(**params)
    if args.print:
      print(result)

    if args.output:
      if args.output == 'auto':
        params.pop('vms')
        csv = ",".join('%s=%s' % (k,v) for k,v in sorted(params.items()))
        fname = 'results/%s/%s_%s.pickle' % (gethostname(), func.__name__, csv)
      else:
        fname = args.output
      print("pickling to", fname)
      pickle.dump(Struct(args=args, result=result), open(fname, "wb"))
