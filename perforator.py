#!/usr/bin/env python3
from collections import defaultdict
from itertools import permutations
from threading import Thread
from statistics import mean
from socket import gethostname
from subprocess import DEVNULL, Popen
from os.path import exists
from os import urandom
from random import choice
from time import sleep
import argparse
import pickle
import time

from perf.perftool import NotCountedError
from perf.utils import wait_idleness
from useful.small import dictzip, invoke
from useful.mystruct import Struct
from config import basis, VMS, IDLENESS, BOOT_TIME
from perf.numa import topology

from useful.mstring import prints

from libvmc import __version__ as vmc_version
assert vmc_version >= 20


class Setup:
  """ Launch all VMS at start, stop them at exit. """

  def __init__(self, vms, benchmarks, debug=False):
    self.benchmarks = benchmarks
    self.vms = vms
    self.debug = debug
    if any([vm.kill() for vm in vms]):
      print("giving old VMs time to die...")
      sleep(3)
    if any(vm.pid for vm in vms):
      raise Exception("there are VMs still running!")
    if any([vm.start() for vm,bmark in zip(vms, benchmarks)]):
      print("let VMs to boot")
      sleep(10)
    else:
      print("no VM start was requested")

  def __enter__(self):
    map = {}
    if not self.debug:
      wait_idleness(IDLENESS*6)
    for bname, vm in zip(self.benchmarks, self.vms):
      #print("{} for {} {}".format(bname, vm.name, vm.pid))
      cmd = basis[bname]
      vm.pipe = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
      vm.bname = bname
    return map

  def __exit__(self, *args):
    print("tearing down the system")
    for vm in self.vms:
      if not vm.pid:
        print(vm, "already dead, not stopping it on tear down")
        continue
      vm.unfreeze()
      vm.shared()
      if not hasattr(vm, "pipe") or vm.pipe is None:
        continue
      ret = vm.pipe.poll()
      if ret is not None:
        print("Test {bmark} on {vm} died with {ret}! Manual intervention needed\n\n" \
              .format(bmark=vm.bname, vm=vm, ret=ret))
        import pdb; pdb.set_trace()
      # vm.pipe.killall() TODO: hangs after tests. VMs frozen?
    #for vm in self.vms:
    #  vm.stop()
    [vm.kill() for vm in VMS]


def cpu_enum():
  """ Enumerate CPU cores, sibblings have adjacent numbers. """
  from copy import copy
  ranked = []
  cpus = copy(topology.all)
  print("all cpus", cpus)
  while cpus:
    cpu = cpus.pop(0)
    ranked.append(cpu)
    sibblings = topology.get_thread_sibling(cpu)
    assert len(sibblings) == 1, "only one sibbling is allowed"
    sibbling = sibblings[0]
    ranked.append(sibbling)
    cpus.remove(sibbling)
  print("CPU cores sorted by sibblings:", ranked)
  return ranked


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


def ragged(time:int=10, interval:int=1, vms=None):
  from functools import partial
  from qemu import ipcistat
  f = partial(ipcistat, events=['cycles','instructions', 'cache-misses', 'minor-faults'], time=10.0, interval=1)
  args = [(vm,) for vm in vms]
  threadulator(f, args)


def isolated_sampling(num:int=1,
                      interval:int=100,
                      pause:float=0.1,
                      delay:float=None,
                      result=None,
                      vms=None):
  """ Isolated sampling. """
  if result is None:
    result = defaultdict(list)

  for vm in vms:
    vm.exclusive()
    for i in range(num):
      if pause: sleep(pause)
      try:
        if delay: sleep(delay)
        ipc = vm.ipcstat(interval)
        result[vm].append(ipc)
      except NotCountedError:
        print("cannot get isolated performance for", vm, vm.bname)
        pass
    vm.shared()

  return result


def shared_sampling(num:int=1,
                    interval:int=100,
                    pause:float=0.1,
                    result=None,
                    vms=None):
  if result is None:
    result = defaultdict(list)

  for i in range(num):
    for vm in vms:
      try:
        ipc = vm.ipcstat(interval)
        result[vm].append(ipc)
      except NotCountedError:
        print("cannot get shared performance for", vm, vm.bname)
        pass
      if pause:
        sleep(pause)

  return result


def shared_thr_sampling(num:int=1,
                        interval:int=100,
                        pause:float=0.0,
                        result=None,
                        vms=None):
  if result is None:
    result = defaultdict(list)

  threads = []
  for vm in vms:
    def f(vm=vm):
      for i in range(num):
        try:
          ipc = vm.ipcstat(interval)
          result[vm].append(ipc)
        except NotCountedError:
          print("cannot get shared performance for", vm, vm.bname)
          pass
        if pause:
          sleep(pause)

    threads.append(Thread(target=f))
  [t.start() for t in threads]
  [t.join() for t in threads]

  return result


def freezing_sampling(num:int,
                      interval:int,
                      pause:float=0.1,
                      delay:float=0.0,
                      result=None,
                      vms=None):
  """ Like freezing, but with another order of loops. """
  if result is None:
    result = defaultdict(list)

  for _ in range(num):
    for i, vm in enumerate(vms):
      if pause: sleep(pause)
      vm.exclusive()
      try:
        if delay: sleep(delay)
        ipc = vm.ipcstat(interval)
        result[vm].append(ipc)
      except NotCountedError:
        print("cannot get frozen performance for", vm, vm.bname)
        pass
      vm.shared()
  return result


def isolated_vs_shared(num:int=10, interval:int=100, pause:float=0.1, vms=None):
  isolated = defaultdict(list)
  shared   = defaultdict(list)
  step = 10
  assert not num % step, "num should be a multiple of %s" % step
  for i in range(num//step):
    print("step {} of {}".format(i+1, num//step))
    isolated_sampling(num=step, interval=interval, pause=pause, result=isolated, vms=vms)
    shared_sampling(num=step,   interval=interval, pause=pause, result=shared,   vms=vms)
  return Struct(isolated=isolated, shared=shared)


def loosers(num:int=10, interval:int=100, pause:float=0.0, vms=None):
  """ Detect starving applications. """
  shared_perf = defaultdict(list)
  frozen_perf = defaultdict(list)
  while num>0:
    print(num, "measurements left")
    shared_sampling(num=10, interval=interval, pause=pause, result=shared_perf, vms=vms)
    freezing_sampling(num=10, interval=interval, pause=pause, result=frozen_perf, vms=vms)
    num -= 10

  result = {}
  for bench, sh_perf, fr_perf in dictzip(shared_perf, frozen_perf):
    ratio = mean(sh_perf) / mean(fr_perf)
    result[bench] = ratio
  print("our technique:")
  print(sorted(result.items(), key=lambda v: v[1]))

  return result


def real_loosers3(num=10, interval=10*1000, pause=0.1, vms=None):
  """ Detect starving applications. Improved version """
  shared_perf = defaultdict(list)
  frozen_perf = defaultdict(list)
  for i,x in enumerate(range(num)):
    print("iteration", i)
    shared_thr_sampling(num=1, interval=interval, result=shared_perf, vms=vms)
    freezing_sampling(num=1,   interval=interval, pause=0.1, result=frozen_perf, vms=vms)
    sleep(pause)

  result = {}
  for vm, sh_perf, fr_perf in dictzip(shared_perf, frozen_perf):
    ratio = mean(sh_perf) / mean(fr_perf)
    result[vm] = ratio
  result = sorted(result.items(), key=lambda v: v[1])
  print("Loosers: straight forward technique:\n", result)

  return result, shared_perf, frozen_perf


def delay(num:int=1, interval:int=100, pause:float=0.1, delay:float=0.01, vms=None):
  """ How delay after freeze affects precision. """
  without   = freezing_sampling(num, interval, pause, 0.0, vms)
  withdelay = freezing_sampling(num, interval, pause, delay, vms)
  print(without)
  print(withdelay)
  print(Struct(without=without, withdelay=withdelay))
  return Struct(without=without, withdelay=withdelay)


def distribution_with_subsampling(num:int=1,
                                  interval:int=100,
                                  pause:float=None,
                                  duty:float=None,
                                  subinterval:int=None,
                                  vms=None):
  """ Intervals are in ms. Duty cycle is in (0,1] range. """
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
        #print("saving quasi to", vm.bname, ipc)
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
        #print("saving sub-sampled to", vm.bname, ipc)
      except NotCountedError:
        print("missed data point for", vm.bname)
        pass
      finally:
        vm.shared()

  return Struct(standard=standard, withskip=withskip)


def distribution(num:int=1, interval:int=100, pause:float=0.1, delay:float=None, vms=None):
  """ How ideal performance looks like in isolated and quasi-isolated environments. """
  isolated  = defaultdict(list)
  frozen    = defaultdict(list)
  batch_size = 10
  assert num % batch_size == 0,  \
      "number of samples should divide by 10, got %s" % num
  iterations = num // batch_size
  for i in range(iterations):
    print("interval %s: %s out of %s" % (interval, i, iterations))
    isolated_sampling(num=batch_size, interval=interval, pause=pause, delay=delay, result=isolated, vms=vms)
    freezing_sampling(num=batch_size, interval=interval, pause=pause, delay=delay, result=frozen, vms=vms)
  return Struct(isolated=isolated, frozen=frozen)


def distribution_with_subsampling2(num:int=1,
                                  interval:int=100,
                                  pause:float=None,
                                  duty:float=None,
                                  subinterval:int=None,
                                  vms=None):
  """ Intervals are in ms. Duty cycle is in (0,1] range. """
  from qemu import ipcistat  # lazy loading

  assert not (pause and duty), "accepts either pause or duty"
  if duty:
    pause = (interval / duty) / 1000  # in seconds
  elif not pause:
    pause = 0.1

  isolated  = defaultdict(list)
  frozen    = defaultdict(list)
  batch_size = 10
  assert num % batch_size == 0,  \
      "number of samples should divide by 10, got %s" % num
  iterations = num // batch_size

  for i in range(iterations):
    print("interval %s: %s out of %s" % (interval, i, iterations))
    isolated_sampling(num=batch_size, interval=interval, pause=pause, result=isolated, vms=vms)


    for i in range(num):
      for vm in vms:
        sleep(pause)
        try:
          vm.exclusive()
          ipc = ipcistat(vm, interval=interval, subinterval=subinterval)
          frozen[vm.bname].append(ipc)
          #print("saving sub-sampled to", vm.bname, ipc)
        except NotCountedError:
          print("missed data point for", vm.bname)
          pass
        finally:
          vm.shared()

    freezing_sampling(num=batch_size, interval=interval, pause=pause, result=frozen, vms=vms)

  return Struct(isolated=isolated, frozen=frozen)


def syswide_stat(time:float=10, vms=[]):
  from perf import perftool
  print("measuring system wide kvm stats %ss" % time)
  performance = perftool.ipc(guest=True, systemwide=True, time=time)
  print("{:.3f}".format(performance))


def start_stop_time(num:int=10, pause:float=0.1, vms=None):
  exclusive = []
  shared    = []
  for i in range(num):
    for vm in vms:
      t = - time.time()
      vm.exclusive()
      t += time.time()
      exclusive.append(t)

      if pause:
        time.sleep(pause)

      t = - time.time()
      vm.shared()
      t += time.time()
      shared.append(t)

  print("shared: {shared}, exclusive: {exclusive}, shared+exclusive: {both}"
        .format(shared=mean(shared),
                exclusive=mean(exclusive),
                both=(mean(shared+exclusive))))


def isolated_perf(vms):
  from subprocess import check_call
  import shlex

  benchmarks = "matrix wordpress blosc static sdag sdagp pgbench ffmpeg".split()
  for bname, vm in zip(benchmarks, vms):
    #if bname != 'wordpress':
    #  continue
    wait_idleness(IDLENESS*6)
    cmd = basis[bname]
    pipe = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
    sleep(10)

    PERF = "/home/sources/perf_lite"
    CMD = "{perf} kvm stat -e instructions,cycles -o {out} -x, -I {subinterval} -p {pid} sleep {sleep}"
    out = "results/limit/isolated_perf_%s.csv" % bname
    cmd = CMD.format(perf=PERF, pid=vm.pid,
                     out=out, subinterval=100, sleep=180)
    check_call(shlex.split(cmd))

    ret = pipe.poll()
    if ret is not None:
      print("Test {bmark} on {vm} died with {ret}! Manual intervention needed\n\n" \
            .format(bmark=bname, vm=vm, ret=ret))
      import pdb; pdb.set_trace()
    pipe.killall()


def perfstat_sampling(num:int=100, interval:int=100, pause:float=0.1, delay:float=0.002, vms=None):
  from perf.numa import get_cur_cpu
  from perfstat import Perf

  isolated  = defaultdict(list)
  frozen    = defaultdict(list)
  batch_size = 5
  assert num % batch_size == 0,  \
      "number of samples should divide by 10, got %s" % num
  iterations = num // batch_size
  perfs = [Perf(cpu=get_cur_cpu(vm.pid)) for vm in vms]

  for i in range(1, iterations+1):
    print(i, "out of", iterations)
    # frozen
    for j in range(batch_size):
      for vm, perf in zip(vms, perfs):
        bmark = vm.bname
        if pause: sleep(pause)
        vm.exclusive()
        sleep(delay)
        stat = perf.measure(interval)
        if stat[0] and stat[1]:
          ipc = stat[0] / stat[1]
          frozen[bmark].append(ipc)
        else:
          print("Perf() missed a datapoint")
        vm.shared()

    # isolated
    for vm, perf in zip(vms, perfs):
      vm.exclusive()
      bmark = vm.bname
      for i in range(batch_size):
        if pause: sleep(pause)
        stat = perf.measure(interval)
        if stat[0] and stat[1]:
          ipc = stat[0] / stat[1]
          isolated[bmark].append(ipc)
        else:
          print("Perf() missed a datapoint")
      vm.shared()

  return Struct(isolated=isolated, frozen=frozen)



# TODO: name collision???
def start_stop(num:int,
               interval:int,
               pause:float=0.1,
               vms=None):
  import shlex
  """ Like freezing, but do not make any. """
  for vm in vms:
    if vm.bname == 'sdag':
      break


  PERF = "/home/sources/perf_lite"
  CMD = "{perf} kvm stat -e instructions,cycles -o {out} -x, -I {subinterval} -p {pid}"
  out = "results/limit/start_stop_f_subint1_%s.csv" % vm.bname
  cmd = CMD.format(perf=PERF, pid=vm.pid, out=out, subinterval=1)
  p = Popen(shlex.split(cmd))

  for i in range(1, num+1):
    #print("%s out of %s" % (i, num))
    if pause:
      sleep(pause)
    vm.exclusive()
    sleep(interval/1000)
    vm.shared()
  print("done")
  p.send_signal(2)  # SIGINT
  return None

def dummy(pause:int=6666666, *args, **kwargs):
  print("got args:", args, kwargs)
  print("NOW DOING NOTHING FOR %ss" % pause)
  sleep(pause)


def dummy_opt(pause:int=6666666, vms=[]):
  from perf.numa import topology
  allocs = [
    ("mine", topology.no_ht),
  ]
  for alloc_name, alloc in allocs:
    #assert len(vms) == len(alloc)
    input("press any key to optimize with %s: %s" % (alloc_name, alloc))
    for cpu, vm in zip(alloc, vms):
      vm.set_cpus([cpu])
  sleep(pause)


def mychoice(l):
  rndbyte = ord(urandom(1))
  return l[rndbyte%len(l)]


def sysperf(t=1):
  from perf import perftool
  stat = perftool.kvmstat(time=t, events="instructions cycles".split(), systemwide=True)
  ipc = stat['instructions'] / stat['cycles']
  performance = stat['instructions'] / (1000**3)
  return performance, ipc


def dead_opt(vms=None):
  """ Optimize applications when dense packed. """
  ranked = cpu_enum()
  for vm,cpu in zip(vms, ranked):
    if not vm.bname:
      break
    if vm.bname == 'matrix':
      vm.set_cpus([3])
    else:
      vm.set_cpus([cpu])
    print("assignment: {bmark}: {cpu}".format(bmark=vm.bname, cpu=cpu))

  sleep(1)  # just in case

  stats, _, _ = real_loosers3(vms=vms)
  return stats


def report(header, t=30):
  performance, ipc = sysperf(t=t)
  print("{header}: {perf:.2f}B insns, ipc: {ipc:.4f}"
        .format(header=header, perf=performance, ipc=ipc))
  return performance, ipc


def dead_opt_n(n=4, num=10, vms=None):
  """ Dead-simple optimization of partial loads. """
  cpus_ranked = cpu_enum()
  report("before start")
  benchmarks = list(basis.items())
  # SPAWN
  active_vms = []
  active_cpus = []
  benches = "matrix sdagp matrix sdagp".split()
  for i, vm, cpu in zip(range(n), vms, cpus_ranked):
    #bmark, cmd = choice(benchmarks)
    bmark = benches.pop(0)
    cmd = basis[bmark]
    print(cpu, bmark, vm)
    vm.pipe = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
    vm.bname = bmark
    vm.set_cpus([cpu])
    active_cpus.append(cpu)
    active_vms.append(vm)

  print("warm-up, active vms:", active_vms)
  sleep(90)

  stats, _, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  p1, ipc1 = report("after finding loosers")
  print(stats)
  for i, (vm, degr) in zip(range(2), stats):
    print(vm, vm.bname)
    for cpu in topology.no_ht:
      if cpu not in active_cpus:
        #TODO: remove old cpu
        vm.set_cpus([cpu])
        active_cpus.append(cpu)

  stats, _, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  p2, ipc2 = report("after fixing loosers")
  print("SPEEDUP", p2/p1)


def dead_opt_new(nr_vms:int=4, nr_perf_samples:int=10, repeat:int=10, vms=None):
  """ Like old one but reports more data. """
  sys_speedup = []
  vm_speedup  = []
  for x in range(repeat):
    print(time.time())
    wait_idleness(IDLENESS*4)
    sys, vm = dead_opt1(n=nr_vms, num=nr_perf_samples, vms=vms)
    sys_speedup.append(sys)
    vm_speedup += vm
  return Struct(sys_speedup=sys_speedup, vm_speedup=vm_speedup)


def dead_opt1(n:int=4, num:int=10, vms=None):
  """ Like dead_opt_n but more output stats so we can add more plots to the article"""
  [vm.start() for vm in vms]
  cpus_ranked = cpu_enum()

  #report("before start")
  # SPAWN
  active_vms = []
  active_cpus = []
  #benchmarks = "matrix sdagp matrix sdagp".split()
  benchmarks = list(basis.keys())
  for i, vm, cpu in zip(range(n), vms, cpus_ranked):
    #bmark, cmd = choice(benchmarks)
    bmark = benchmarks.pop(0)
    cmd = basis[bmark]
    print(cpu, bmark, vm)
    vm.pipe = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
    vm.bname = bmark
    vm.set_cpus([cpu])
    active_cpus.append(cpu)
    active_vms.append(vm)
    sleep(0.2)  # do not start them all simultaneusly

  print("warm-up, active vms:", active_vms)
  sleep(5)
  print("TODO: shorter sleep")

  stats, perf_before, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  p1, ipc1 = report("after finding loosers")
  print(stats)
  relocated_vms = []
  for i, (vm, degr) in zip(range(2), stats):
    print(vm, vm.bname)
    relocated_vms.append(vm)
    for cpu in topology.no_ht:
      if cpu not in active_cpus:
        #TODO: remove old cpu
        vm.set_cpus([cpu])
        active_cpus.append(cpu)

  stats_after, perf_after, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  prints("BEFORE: {perf_before}\n AFTER: {perf_after}")
  p2, ipc2 = report("after fixing loosers")

  for vm in vms:
    if hasattr(vm, "pipe") and vm.pipe:
      vm.pipe.killall()
      vm.pipe = None

  # RESULT
  sys_speedup = p2 / p1
  vm_speedup  = []
  #for vm in perf_after.keys():
  for vm in relocated_vms:
    r = mean(perf_after[vm]) / mean(perf_before[vm])
    vm_speedup.append(r)
  print("SPEEDUP:", sys_speedup)
  print("IMPROVEMENTS:", vm_speedup)
  return sys_speedup, vm_speedup


def power_consumption(n=4, num=10, vms=None):
  """ Dead-simple optimization of partial loads. """
  cpus_ranked = cpu_enum()
  def report(header, t=30):
    performance, ipc = sysperf(t=t)
    print("{header}: {perf:.2f}B insns, ipc: {ipc:.4f}"
          .format(header=header, perf=performance, ipc=ipc))
    return performance, ipc

  report("before start", t=3)

  # SPAWN
  active_vms = []
  active_cpus = []
  benchmarks = list(basis.items())
  for i, vm, cpu in zip(range(n), vms, cpus_ranked):
    bmark, cmd = choice(benchmarks)
    print(cpu, bmark, vm)
    vm.pipe = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
    vm.bname = bmark
    vm.set_cpus([cpu])
    active_cpus.append(cpu)
    active_vms.append(vm)

  input("press enter when done")

  stats, _, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  p1, ipc1 = report("after finding loosers")
  print(stats)
  for i, (vm, degr) in zip(range(2), stats):
    print(vm, vm.bname)
    for cpu in topology.no_ht:
      if cpu not in active_cpus:
        for oldcpu in vm.cpus:
          active_cpus.remove(oldcpu)
        vm.set_cpus([cpu])
        active_cpus.append(cpu)
  print("RELOCATION DONE")

  stats, _, _ = real_loosers3(interval=1*1000, num=num, vms=active_vms)
  p2, ipc2 = report("after fixing loosers")
  print("SPEEDUP", p2/p1)
  input("press enter when done")


def llc_classify(interval:int=180*1000, vms=None):
  events = ['instructions', 'cycles', 'LLC-stores', 'stalled-cycles-frontend', 'L1-dcache-stores']
  shared = {}
  isolated = {}
  for vm in vms:
    try:
      stat = vm.stat(interval=interval, events=events)
      shared[vm.bname] = stat
    except NotCountedError:
      print("missed data point")
  for vm in vms:
    try:
      vm.exclusive()
      stat = vm.stat(interval=interval, events=events)
      isolated[vm.bname] = stat
    except NotCountedError:
      print("missed data point")
    finally:
      vm.shared()
  print("SHARED:\n", shared)
  print("ISOLATED:\n", isolated)


def isolated_performance(interval:int=180*1000, warmup:int=15, vms=None):
  for vm in vms[1:]:
    vm.stop()
  vm = vms[0]
  vm.start()
  sleep(BOOT_TIME)
  cpu = topology.no_ht[0]
  vm.set_cpus([cpu])

  result = {}
  for bmark, cmd in basis.items():
    wait_idleness(IDLENESS*4)
    print("measuring", bmark)
    vm.Popen(cmd)
    sleep(warmup)

    ipc = vm.ipcstat(interval)
    result[bmark] = ipc

    ret = vm.pipe.poll()
    if ret is not None:
      print("Test {bmark} on {vm} died with {ret}! Manual intervention needed\n\n" \
            .format(bmark=bmark, vm=vm, ret=ret))
      import pdb; pdb.set_trace()
    vm.pipe.killall()

  print(result)
  return result


def all_events(interval:int=180*1000, warmup:int=15, vms=None):
  from perf import perftool
  events = perftool.get_events()
  print("monitoring events:", events)
  for vm in vms[1:]:
    vm.stop()
  vm = vms[0]
  vm.start()
  sleep(BOOT_TIME)
  cpu = topology.no_ht[0]
  vm.set_cpus([cpu])

  result = {}
  for bmark, cmd in basis.items():
    wait_idleness(IDLENESS*4)
    print("measuring", bmark)
    vm.Popen(cmd)
    sleep(warmup)

    ipc = vm.stat(interval=interval, events=events)
    result[bmark] = ipc

    ret = vm.pipe.poll()
    if ret is not None:
      print("Test {bmark} on {vm} died with {ret}! Manual intervention needed\n\n" \
            .format(bmark=bmark, vm=vm, ret=ret))
      import pdb; pdb.set_trace()
    vm.pipe.killall()

  print(result)
  return result


from itertools import product
def interference(interval:int=180*1000, warmup:int=15, mode=None, vms=None):
  assert mode in ['sibling', 'distant']
  if mode == 'sibling':
    cpu1 = topology.no_ht[0]
    cpu2 = topology.ht_map[cpu1][0]
  else:
    cpu1, cpu2 = topology.no_ht[:2]

  print("stopping all but 2 vms because we need only two")
  for vm in vms[2:]:
    vm.stop()
  vm1, vm2 = vms[:2]
  vm1.start()
  vm2.start()

  sleep(13)
  vm1.set_cpus([cpu1])
  vm2.set_cpus([cpu2])

  benchmarks = list(sorted(basis))
  result = defaultdict(lambda: [None, None])
  for bmark1, bmark2 in product(benchmarks, repeat=2):
    if (bmark2, bmark1) in result:
      continue
    key = (bmark1, bmark2)
    print(key)

    wait_idleness(IDLENESS*6)
    p1 = vm1.Popen(basis[bmark1])
    sleep(1)  # reduce oscillation when two same applications are launched
    p2 = vm2.Popen(basis[bmark2])
    sleep(warmup)

    def get_ipc(idx, vm):
      ipc = vm.ipcstat(interval)
      result[key][idx] = ipc
    threadulator(get_ipc, [(0, vm1), (1, vm2)])

    print(result)
    for vm in [vm1, vm2]:
      ret = vm.pipe.poll()
      if ret is not None:
        print("Test {bmark} on {vm} died with {ret}! Manual intervention needed\n\n" \
              .format(bmark=vm.bname, vm=vm, ret=ret))
        import pdb; pdb.set_trace()

    p1.killall()
    p2.killall()



if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Run experiments')
  parser.add_argument('-o', '--output', default=None, help="Where to put results")
  parser.add_argument('-w', '--warmup', default=10, type=int, help="Warmup time")
  parser.add_argument('-d', '--debug', default=False, const=True, action='store_const', help='enable debug mode')
  parser.add_argument('-t', '--test', help="test specification")
  parser.add_argument('-p', '--print', default=False, const=True, action='store_const', help='print result')
  parser.add_argument('-b', '--benches', nargs='*', default="matrix wordpress blosc static sdag sdagp pgbench ffmpeg".split(), help="which benchmarks to run")
  args = parser.parse_args()
  print("config:", args)

  assert not args.output or not exists(args.output), "output %s already exists" % args.output

  from perf.numa import pin_task
  import os
  pin_task(os.getpid(), 6)

  with Setup(VMS, args.benches, debug=args.debug):
    if not args.debug and args.benches:
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
        string_fargs = ",".join('%s=%s' % (k,v) for k,v in sorted(fargs.items()))
        fname = 'results/{host}/{f}_{fargs}.pickle'  \
                .format(host=gethostname(), f=f.__name__, fargs=string_fargs)
      else:
        fname = args.output
      print("pickling to", fname)
      pickle.dump(Struct(f=f.__name__, fargs=fargs, result=result, prog_args=args),
                  open(fname, "wb"))
