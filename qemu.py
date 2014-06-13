#!/usr/bin/env python3

from perf.qemu import Template
from perf.numa import topology
from perf.perftool import NotCountedError  #TODO: import *stat
from libvmc import Drive, Bridged, main, manager
from subprocess import check_call
from socket import socketpair
from collections import defaultdict
import shlex

from config import VMS as vms

PERF = "/home/sources/abs/core/linux/src/linux-3.14/tools/perf/perf"

def kvmistat(pid, events, time, interval):
  CMD = "{perf} kvm stat -e {events} --log-fd {fd} -x, -I {interval} -p {pid} sleep {time}"
  read, write = socketpair()
  cmd = CMD.format(perf=PERF, pid=pid, events=",".join(events), \
                   fd=write.fileno(), interval=interval, time=time)
  check_call(shlex.split(cmd), pass_fds=[write.fileno()])  # TODO: buf overflow??
  result = read.recv(100000).decode()
  r = defaultdict(list)
  nc = 0
  for s in result.splitlines():
    try:
      _,rawcnt,_,ev = s.split(',')
    except Exception as err:
      print(s,err)
      continue
    if rawcnt == '<not counted>':
      nc += 1
      continue
    r[ev].append(int(rawcnt))
  ratio = nc/len(result.splitlines())
  if ratio > 0.3:
    print("nc", nc, ratio)
  return r


def kvmstat(pid, events, time):
  CMD = "{perf} kvm stat -e {events} --log-fd {fd} -x, -p {pid} sleep {time}"
  read, write = socketpair()
  cmd = CMD.format(perf=PERF, pid=pid, events=",".join(events), \
                   fd=write.fileno(), time=time)
  check_call(shlex.split(cmd), pass_fds=[write.fileno()])  # TODO: buf overflow??
  result = read.recv(100000).decode()
  r = {}
  for s in result.splitlines():
    rawcnt,_,ev = s.split(',')
    if rawcnt == '<not counted>':
      raise NotCountedError
    r[ev] = int(rawcnt)
  return r


if __name__ == '__main__':
  manager.autostart_delay = 0
  main()
