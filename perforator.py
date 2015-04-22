#!/usr/bin/env python3
from collections import defaultdict
from itertools import permutations
from threading import Thread
from statistics import mean
from socket import gethostname
from subprocess import DEVNULL
from os.path import exists
from time import sleep
import argparse
import pickle

from perf.perftool import NotCountedError
from perf.utils import wait_idleness
from useful.small import dictzip, invoke
from useful.mystruct import Struct
from config import basis, VMS, IDLENESS


class Setup:
  """ Launch all VMS at start, stop them at exit. """
  pipes = None

  def __init__(self, vms, benchmarks, debug=False):
    self.benchmarks = benchmarks
    self.vms = vms
    self.debug = debug
    self.pipes = []
    if any([vm.start() for vm in vms]):
      print("some of vms were not started, giving them time to start")
      sleep(10)

  def __enter__(self):
    map = {}
    if not self.debug:
      wait_idleness(IDLENESS*6)
    for bname, vm in zip(self.benchmarks, self.vms):
      #print("{} for {} {}".format(bname, vm.name, vm.pid))
      cmd = basis[bname]
      p = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
      vm.bname = bname
      self.pipes.append(p)
    return map

  def __exit__(self, *args):
    for vm in self.vms:
      vm.unfreeze()
      vm.shared()
    for p in self.pipes:
      if p.returncode is not None:
        print("ACHTUNG!!!!!!!!\n\n!")
      # p.killall() TODO: hangs after tests. VMs frozen?
    for vm in self.vms:
      vm.stop()

def threadulator(f, params):
  """ Execute routine actions in parallel. """
  threads = []
  for param in params:
    t = Thread(target=f, args=param)
    threads.append(t)
  [t.start() for t in threads]
  [t.join() for t in threads]


def reverse_isolated(num:int, time:float, pause:float, vms=None):
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
  """ How ideal performance looks like in isolated and quasi-isolated environments. """
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


def distribution2(num:int=1,interval:float=0.1, pause:float=0.1, vms=None, label=None):
  """ Like distribution, but with another order of operations. """
  pure = defaultdict(list)
  quasi = defaultdict(list)

  # quasi-isolated performance
  for i in range(num):
    print("step 2: {} out of {}".format(i+1, num))
    for i,vm in enumerate(vms):
      sleep(pause)
      try:
        vm.exclusive()
        ipc = vm.ipcstat(interval)
        quasi[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      finally:
        vm.shared()

  # purely isolated performance
  for vm in vms:
    vm.freeze()

  for i,vm in enumerate(vms):
    print("step 1: {} out of {}".format(i+1, len(vms)))
    vm.unfreeze()
    for _ in range(num):
      sleep(pause)
      try:
        ipc = vm.ipcstat(interval)
        pure[vm.bname].append(ipc)
        print("saving pure to", vm.bname, ipc)
      except NotCountedError:
        pass
    vm.freeze()

  for vm in vms:
    vm.unfreeze()

  return Struct(pure=pure, quasi=quasi)


def ragged(time:int=10, interval:int=1, vms=None):
  from functools import partial
  from qemu import ipcistat
  f = partial(ipcistat, events=['cycles','instructions', 'cache-misses', 'minor-faults'], time=10.0, interval=1)
  args = [(vm,) for vm in vms]
  threadulator(f, args)


def shared(num:int=1, interval:float=0.1, pause:float=0.1, vms=None):
  result = defaultdict(list)

  for i in range(num):
    if i%10 == 0:
      print("step 1: {} out of {}".format(i+1, num))
    for vm in vms:
      try:
        ipc = vm.ipcstat(interval)
        result[vm.bname].append(ipc)
      except NotCountedError:
        print("cannot get shared performance for", vm.bname)
        pass
      if pause:
        sleep(pause)

  return result


def freezing(num:int, interval:float, pause:float, delay:float=0.0, vms=None):
  """ Measure IPC of individual VMS in freezing environment. """
  result = defaultdict(list)
  for i,vm in enumerate(vms):
    #print("{} out of {} for {}".format(i+1, len(vms), vm.bname))
    for _ in range(num):
      if pause: sleep(pause)
      vm.exclusive()
      if delay: sleep(delay)
      try:
        ipc = vm.ipcstat(interval)
        result[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()
  return result


def freezing2(num:int, interval:float, pause:float, delay:float=0.0, vms=None):
  """ Like freezing, but with another order of loops. """
  result = defaultdict(list)
  for _ in range(num):
    for i,vm in enumerate(vms):
    #print("{} out of {} for {}".format(i+1, len(vms), vm.bname))
      if pause: sleep(pause)
      vm.exclusive()
      if delay: sleep(delay)
      try:
        ipc = vm.ipcstat(interval)
        result[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()
  return result


def loosers(num:int=10, interval:float=0.1, pause:float=0.0, vms=None):
  """ Detect starving applications. """
  shared_perf = shared(num=num, interval=interval, pause=pause, vms=vms)
  frozen_perf = freezing2(num=num, interval=interval, pause=pause, vms=vms)
  result = {}
  for bench, sh_perf in shared_perf.items():
    fr_perf = frozen_perf[bench]
    ratio = mean(sh_perf) / mean(fr_perf)
    result[bench] = ratio
  print(sorted(result.items(), key=lambda v: v[1]))
  return result


def delay(num:int=1, interval:float=0.1, pause:float=0.1, delay:float=0.01, vms=None):
  """ How delay after freeze affects precision. """
  without   = freezing(num, interval, pause, 0.0, vms)
  withdelay = freezing(num, interval, pause, delay, vms)
  print(without)
  print(withdelay)
  print(Struct(without=without, withdelay=withdelay))
  return Struct(without=without, withdelay=withdelay)


"""
def distr_subsampling(num:int=1, interval:float=0.1, pause:float=0.1, rate:int=100, skip:int=2, vms=None):
  standard = defaultdict(list)
  withskip = defaultdict(list)
  subinterval = 1000 // rate

  # STEP 1: normal freezing approach
  print("!!!", vms)
  for i,vm in enumerate(vms):
    print("step 2: {} out of {} for {}".format(i+1, len(vms), vm.bname))
    for _ in range(num):
      sleep(pause)
      vm.exclusive()
      try:
        ipc = vm.ipcstat(interval)
        standard[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()

  # STEP 2: approach with sub-sampling and skip
  from qemu import ipcistat
  for i,vm in enumerate(vms):
    print("step 2: {} out of {} for {}".format(i+1, len(vms), vm.bname))
    for _ in range(num):
      sleep(pause)
      vm.exclusive()
      try:
        ipc = ipcistat(vm, time=interval, interval=subinterval, skip=skip)
        withskip[vm.bname].append(ipc)
        print("saving sub-sampled to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()

  return Struct(standard=standard, withskip=withskip)
"""

def distribution_with_subsampling(num:int=1,
                                  interval:int=100,
                                  pause:float=None,
                                  duty:float=None,
                                  subinterval:int=None,
                                  vms=None):
  """ Intervals are in ms. Duty cycle is in (0,1] range.
  """
  from qemu import ipcistat  # lazy loading

  standard = defaultdict(list)
  withskip = defaultdict(list)

  assert not (pause and duty), "accepts either pause or duty"
  if duty:
    pause = (interval / duty) / 1000  # in seconds
  elif not pause:
    pause = 0.1

  for _ in range(num):
    print("step 1: {} out of {}".format(_+1, num))
    # STEP 1: normal freezing approach
    for vm in vms:
      sleep(pause)
      vm.exclusive()
      try:
        ipc = vm.ipcstat(interval)
        standard[vm.bname].append(ipc)
        print("saving quasi to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      vm.shared()

    # STEP 2: approach with sub-sampling and skip
    #print("step 2: {} out of {}".format(_+1, num))
    for vm in vms:
      sleep(pause)
      try:
        vm.exclusive()
        ipc = ipcistat(vm, interval=interval, subinterval=subinterval)
        withskip[vm.bname].append(ipc)
        print("saving sub-sampled to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      finally:
        vm.shared()

  return Struct(standard=standard, withskip=withskip)


def dummy(*args, **kwargs):
  print("got args:", args, kwargs)
  print("NOW DOING NOTTHING")
  sleep(6666666)


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  #parser.add_argument('-s', '--skip', type=int, default=0, help="number of initial samples to skip")
  parser.add_argument('-o', '--output', default=None, help="Where to put results")
  parser.add_argument('-w', '--warmup', default=10, type=int, help="Warmup time")
  parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  parser.add_argument('-t', '--test', help="test specification")
  parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-b', '--benches', nargs='+', default="matrix wordpress blosc static sdag sdagp pgbench ffmpeg".split(), help="which benchmarks to run")
  args = parser.parse_args()
  print("config:", args)

  assert not args.output or not exists(args.output), "output %s already exists" % args.output

  with Setup(VMS, args.benches, debug=args.debug):
    if not args.debug:
      print("benches warm-up for %s seconds" % args.warmup)
      sleep(args.warmup)
    f, fargs = invoke(args.test, globals(), vms=VMS)
    print("invoking", f.__name__, "with", fargs)
    result = f(**fargs)
    if args.print:
      print(result)

    if args.output:
      fargs.pop('vms')
      if args.output == 'auto':
        fargs = ",".join('%s=%s' % (k,v) for k,v in sorted(fargs.items()))
        fname = 'results/{host}/{f}_{fargs}.pickle'  \
                .format(host=gethostname(), f=f.__name__, fargs=fargs)
      else:
        fname = args.output
      print("pickling to", fname)
      pickle.dump(Struct(f=f.__name__, fargs=fargs, result=result, prog_args=args),
                  open(fname, "wb"))
