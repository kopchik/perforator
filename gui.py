#!/usr/bin/env python3

from collections import defaultdict, deque
from threading import Thread, Event
from subprocess import DEVNULL
from statistics import mean
import time
import sys

import psutil

from libgui import Border, Bars, Bar, String, \
  Button, Canvas, XY, Text, CMDInput, VList, \
  HList, Range, mywrapper, loop, t
from perf.qemu import NotCountedError
from perf.numa import topology

from useful.small import readfd, nsplit
from useful.log import Log

from config import VMS, log, basis as bench_cmd


def dictsum(l, key):
  return sum(e[key] for e in l)


class Stat:
  maxlen = 1

  def __init__(self, cpubar, ipcbar, pid):
    self.shared = deque(maxlen=self.maxlen)
    self.isolated = deque(maxlen=self.maxlen)
    self.cpu = deque(maxlen=self.maxlen)
    self.cpubar = cpubar
    self.ipcbar = ipcbar
    self.process = psutil.Process(pid)

  def update_bars(self):
    ipc = self.get_shared_ipc()
    if ipc:
      self.ipcbar.update(ipc)
    self.cpubar.update(mean(self.cpu))

  def get_shared_ipc(self):
    insns  = dictsum(self.shared, 'instructions')
    cycles = dictsum(self.shared, 'cycles')
    if not insns or not cycles:
      return None
    return insns / cycles


class Collector(Thread):
  """ 1. Profile tasks
      1. Update bars and stats
  """
  def __init__(self, vms, stat, ev):
    super().__init__()
    self.stat = stat
    self.vms = vms
    self.ev = ev

  def run(self, measure_time=0.1, interval=0.9):
    stat = self.stat
    vms  = self.vms
    ev   = self.ev
    while True:
      ev.wait()
      time.sleep(interval)
      totins = 0
      for vm in vms:
        # measure CPU
        vmstat = stat[vm]
        cpu = vmstat.process.cpu_percent()
        vmstat.cpu.append(cpu)

        try:
          # TODO! vm.exclusive()
          isolated = vm.ipcstat(measure_time, raw=True)
          vmstat.isolated.append(isolated)

          time.sleep(interval)

          # TODO! vm.shared()
          shared = vm.ipcstat(measure_time, raw=True)
          vmstat.shared.append(shared)
        except NotCountedError:
          pass
        finally:
          vm.shared()
      for st in stat.values():
        st.update_bars()


@mywrapper
def gui():
  num_cores = len(topology.all)
  prof_ev = Event()
  prof_ev.set()

  # top-like bars
  stat = {}  # {vm:Stat() for vm in VMS}
  bars = []
  for vm in VMS:
    cpubar = Bar(fmt="CPU: {:.1f}%", r=Range(0, 100))
    ipcbar = Bar(fmt="IPC: {:.2f}", color=t.white, overflow=t.green)
    stat[vm] = Stat(cpubar, ipcbar, vm.pid)
    bars.append(cpubar)
    bars.append(ipcbar)
  barsWidget = HList(*[VList(*piece) for piece in nsplit(bars, 2)], id='bars')

  # WIDGET HIERARCHY
  root = \
      Border(
          VList(
              Border(
                  Bar(id='cpuload', fmt="{:.1%}"),
                  label="CPU Load (avg. of all cores)"),
              Border(barsWidget,
                     label="Per-VM load and efficiency"),
              Border(
                  Text(id='logwin'),
                  label="Logs"),
              Border(
                  CMDInput(id='cmdinpt'),
                  label="CMD Input"),
              Button("QUIT", cb=sys.exit)),
          label="Per-VM Performance (%s cores)" % num_cores)  # TODO: label may change

  # ON-SREEN LOGGING
  logwin = root['logwin']
  Log.file = logwin
  #Log.file = open('/tmp/test', 'wt')

  # CPU LOAD
  def cpuload():
    with open('/proc/uptime', 'rt') as fd:
      old_uptime, old_idle  = readfd(fd)
      while True:
        time.sleep(1.5)
        uptime, idle  = readfd(fd)
        tot_time = (uptime-old_uptime) * num_cores
        load_time = tot_time - (idle - old_idle)
        cpu_load = load_time / tot_time
        old_uptime, old_idle = uptime, idle
        #log.info("cpu load: {:.1%}".format(cpu_load))
        root['cpuload'].update(cpu_load)
  cputhread = Thread(target=cpuload, daemon=True)
  cputhread.start()

  # CMDLINE
  def cmdcb(s):
    tstamp = time.strftime("%H:%M:%S", time.localtime())
    logwin.println("{} {}".format(tstamp, s))
    if s == 'quit':
      sys.exit()
    elif s == 'bstart':
      benchmarks = "matrix wordpress blosc static sdag sdagp pgbench ffmpeg".split()
      for bname, vm in zip(benchmarks, VMS):
        cmd = bench_cmd[bname]
        p = vm.Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)
        vm.bname = bname
        assert not hasattr(vm, 'pipe')
        vm.pipe = p
    elif s == 'bstop':
      for vm in VMS:
        vm.unfreeze()
        p = vm.pipe
        if p.returncode is not None:
          log.error("for VM %s: task is already dead, dude" % vm)
        p.killall()
    elif s == 'pstop':
      prof_ev.clear()
    elif s == 'pstart':
      prof_ev.set()
    elif s == 'redraw':
      root.canvas.clear()
      root.draw()
  root['cmdinpt'].cb = cmdcb

  collector = Collector(vms=VMS, stat=stat, ev=prof_ev)
  collector.daemon = True
  collector.start()


  # MAIN LOOP
  loop(root)


if __name__ == '__main__':
  gui()
