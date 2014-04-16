#!/usr/bin/env python3

from perf.qemu import Template
from perf.numa import topology
from libvmc import Drive, Bridged, main, manager
#from perflib import Task
from subprocess import check_call
from socket import socketpair
from collections import defaultdict
import shlex

vms = []

def kvmstat(pid, events, time, interval):
  CMD = "perf kvm stat -e {events} --log-fd {fd} -x, -I {interval} -p {pid} sleep {time}"
  read, write = socketpair()
  cmd = CMD.format(pid=pid, events=",".join(events), fd=write.fileno(), interval=interval, time=time)
  print(cmd)
  check_call(shlex.split(cmd), pass_fds=[write.fileno()])  # TODO: buf overflow??
  result = read.recv(100000).decode()
  r = defaultdict(list)
  for s in result.splitlines():
    _,rawcnt,_,ev = s.split(',')
    r[ev].append(int(rawcnt))
  return r


class Template(Template):
  task = None
  def shared(self):
    for vm in vms:
      vm.unfreeze()

  def exclusive(self):
    for vm in vms:
      if vm == self: continue
      vm.freeze()

  def measure(self, interval=1, num=1):
    if not self.task:
      self.task = Task(self.pid)
    return self.task.measurex(interval, num)

  def stat(self, time=1, interval=100):
    r = kvmstat(self.pid, ['instructions', 'cycles'], time, interval)
    ins = r['instructions']
    cycles = r['cycles']
    return ins, cycles

for i, cpu in enumerate(topology.cpus_no_ht):
  vm = Template(
      name = "vm%s"%i,
      auto = True,
      cpus = [i],  # affinity
      net  = [Bridged(ifname="template", model='e1000', mac="52:54:91:5E:38:0%s"%i, br="intbr")],
      drives = [Drive("/home/virtuals/vm%s.qcow2"%i, master="/home/virtuals/research.qcow2", cache="unsafe")],
      addr = "172.16.5.1%s"%i
      )
  vms.append(vm)


if __name__ == '__main__':
  manager.autostart_delay = 0
  main()
