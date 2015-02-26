#!/usr/bin/env python3

from collections import defaultdict, deque
from threading import Thread
from statistics import mean
import curses
import time
import sys

from libgui import Border, Bars, String, Button, Canvas, XY, Text, CMDInput, VList, mywrapper, loop
from perf.qemu import NotCountedError
from perf.numa import topology
from useful.log import Log
from config import VMS, log


def dictsum(l, key):
  return sum(e[key] for e in l)


class Stat:
  maxlen = 10
  def __init__(self):
    self.shared = deque(maxlen=self.maxlen)
    self.isolated = deque(maxlen=self.maxlen)

  def get_shared_ipc(self):
    insns  = dictsum(self.shared, 'instructions')
    cycles = dictsum(self.shared, 'cycles')
    if not insns or not cycles:
      return None
    return insns / cycles

  def get_isolated_ipc(self):
    raise NotImplementedError


class Collector(Thread):
  """ 1. Profile tasks
      1. Update bars and stats
  """
  def __init__(self, vms, stat, cb):
    super().__init__()
    self.stat = stat
    self.vms = vms
    self.cb = cb

  def run(self, measure_time=0.1, interval=0.1):
    stat = self.stat
    vms = self.vms
    cb = self.cb
    while True:
      time.sleep(interval)
      totins = 0
      for vm in vms:
        try:
          vm.exclusive()
          isolated = vm.ipcstat(measure_time, raw=True)
          stat[vm].isolated.append(isolated)

          time.sleep(interval)

          vm.shared()
          shared = vm.ipcstat(measure_time, raw=True)
          stat[vm].shared.append(shared)
        except NotCountedError:
          pass
        finally:
          vm.shared()
      if cb:
        cb()


@mywrapper
def gui(scr):
  num_cores = len(topology.all)

  # WIDGET HIERARCHY
  root = \
      Border(
          VList(
              Border(
                VList(
                  Bars([0.0 for _ in topology.all], id='bars'),
                  String("...", id='bartext'))),
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

  # CMDLINE
  def cmdcb(s):
    tstamp = time.strftime("%H:%M:%S", time.localtime())
    logwin.println("{} {}".format(tstamp, s))
    if s == 'quit':
      sys.exit()
  root['cmdinpt'].cb = cmdcb

  # top-like bars
  vmstat = defaultdict(Stat)
  def update_bars():
    bars = []
    for vm in VMS:
      ipc = vmstat[vm].get_shared_ipc()
      if not ipc:
        log.error("empty stats for %s" % vm)
        ipc = 0.0
      bars.append(ipc)
    root['bars'].update(bars)
    root['bartext'].update("Average IPC: {:.2f}".format(mean(bars)))
    return bars

  collector = Collector(vms=VMS, stat=vmstat, cb=update_bars)
  collector.daemon = True
  collector.start()


  # MAIN LOOP
  # setup canvas
  size_y, size_x = scr.getmaxyx()
  size = XY(size_x, size_y)
  canvas = Canvas(scr, size)
  canvas.clear()

  # calculate widget placement and draw widgets
  root.init(pos=XY(0, 0), maxsize=size, canvas=canvas)
  root.setup_sigwinch()
  root.draw()
  if root.cur_focus:
    root.cur_focus.on_focus()

  loop(scr, root)


if __name__ == '__main__':
  gui()
