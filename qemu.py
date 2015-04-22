#!/usr/bin/env python3

from perf.perftool import NotCountedError
from libvmc import main, manager
from subprocess import check_call
from threading import current_thread
from collections import defaultdict
from statistics import StatisticsError
from os import unlink
import shlex

from config import VMS as vms  # do not remove, this triggers population of config


#PERF = "/home/sources/abs/core/linux/src/linux-3.19/tools/perf/perf"
#PERF = "perf"
PERF = "/home/sources/perf_lite"


def ipcistat(vm, interval, subinterval, events=['cycles', 'instructions']):
  interval = interval / 1000
  nc = 0  # num of not counted events
  CMD = "{perf} kvm stat -e {events} -o {out} -x, -I {subinterval} -p {pid} sleep {interval}"
  out = "/tmp/perf_%s_%s" % (vm.bname, current_thread().ident)
  cmd = CMD.format(perf=PERF, pid=vm.pid, events=",".join(events),
                   out=out, subinterval=subinterval, interval=interval)
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
      _, rawcnt, _, ev = s.split(',')
    except ValueError:
      continue
    if rawcnt == '<not counted>':
      print('missing subsample')
      nc += 1
      rawcnt = 0
    r[ev].append(int(rawcnt))
  instructions = r['instructions']
  cycles = r['cycles']
  assert len(instructions) == len(cycles)
  for pos, (i, c) in enumerate(zip(instructions, cycles)):
    if i == 0 or c == 0:
      instructions[pos] = cycles[pos] = 0

  nc = 0
  ratio = nc/len(result.splitlines())
  if ratio > 0.3:
    print("nc", nc, ratio)
  try:
    return {'instructions': instructions, 'cycles': cycles}
  except (ZeroDivisionError, StatisticsError):
    print(cmd)
    raise NotCountedError


if __name__ == '__main__':
  manager.autostart_delay = 0
  main()
