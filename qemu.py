#!/usr/bin/env python3

from perf.qemu import Template
from perf.numa import topology
from perf.perftool import NotCountedError
from libvmc import Drive, Bridged, main, manager
from subprocess import check_call
from socket import socketpair
from threading import current_thread
from collections import defaultdict
from statistics import mean
from os import unlink
import shlex

from config import VMS as vms  #do not remove, this triggers population of config


PERF = "/home/sources/abs/core/linux/src/linux-3.14/tools/perf/perf"


def ipcistat(vm, time, interval, events=['cycles','instructions'], skip=0):
  nc = 0  # num of not counted events
  CMD = "{perf} kvm stat -e {events} -o {out} -x, -I {interval} -p {pid} sleep {time}"
  out = "/tmp/perf_%s_%s" % (vm.bname, current_thread().ident)
  cmd = CMD.format(perf=PERF, pid=vm.pid, events=",".join(events), \
                   out=out, interval=interval, time=time)
  try:
    check_call(shlex.split(cmd))
  except:
    raise NotCountedError
  with open(out) as fd:
    result = fd.read()
  unlink(out)

  r = defaultdict(list)
  for s in result.splitlines():
    try:
      _,rawcnt,_,ev = s.split(',')
    except ValueError as err:
      continue
    if rawcnt == '<not counted>':
      print('missing subsample')
      nc += 1
      rawcnt = 0
    r[ev].append(int(rawcnt))
  instructions = r['instructions']
  cycles = r['cycles']
  assert len(instructions) == len(cycles)
  for pos, (i,c) in enumerate(zip(instructions, cycles)):
    if i == 0 or c == 0:
      instructions[pos] = cycles[pos] = 0

  nc = 0
  ratio = nc/len(result.splitlines())
  if ratio > 0.3:
    print("nc", nc, ratio)
  try:
    return mean(instructions[skip:]) / mean(cycles[skip:])
  except ZeroDivisionError:
    raise NotCountedError

if __name__ == '__main__':
  manager.autostart_delay = 0
  main()
