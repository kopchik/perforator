#!/usr/bin/env python3

from collections import defaultdict, deque
from threading import Thread
import curses
import time
import sys

from libgui import Border, Bars, String, Button, Canvas, XY, Text, CMDInput, VList, mywrapper
from perf.qemu import NotCountedError
from useful.log import Log
from config import VMS, log
from statistics import mean


class Stat:
  def __init__(self):
    self.shared = deque(maxlen=10)
    self.isolated = deque(maxlen=10)


def collect(vms, vmstat, measure_time=0.1, interval=0.1, cb=None):
  while True:
    time.sleep(interval)
    if cb:
      cb()
    for vm in vms:
      try:
        vm.exclusive()
        isolated = vm.ipcstat(measure_time)

        time.sleep(interval)

        vm.shared()
        shared = vm.ipcstat(measure_time)

        vmstat[vm].isolated.append(isolated)
        vmstat[vm].shared.append(shared)
      except NotCountedError:
        pass
      finally:
        vm.shared()


@mywrapper
def gui(scr):
  # WIDGET HIERARCHY
  root = \
      Border(
          VList(
              Border(
                VList(
                  Bars([0.0 for _ in range(8)], id='bars'),
                  String("...", id='bartext'))),
              Border(
                  Text(id='logwin'),
                  label="Logs"),
              Border(
                  CMDInput(id='cmdinpt'),
                  label="CMD Input"),
              Button("QUIT", cb=sys.exit)),
          label="Per-VM Performane")  # TODO: label may change

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
      stat = vmstat[vm]
      if not stat.shared or not stat.isolated:
        log.error("empty stats for %s" % vm)
        result = 0.0
      else:
        shared = mean(stat.shared)
        isolated = mean(stat.isolated)
        result = shared / isolated
      bars.append(result)
    root['bars'].update(bars)
    root['bartext'].update("Average IPC: {:.2f}".format(mean(bars)))
    return bars

  collector = Thread(target=collect,
                      args=(VMS, vmstat),
                      kwargs={'cb': update_bars}
              )
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

  while True:
    try:
      key = scr.getkey()
    except KeyboardInterrupt:
      break
    except curses.error:
      # this is very likely to caused by terminal resize O_o
      continue
    if key == '\x1b':
      break
    if root.cur_focus:
      root.cur_focus.input(key)


if __name__ == '__main__':
  gui()
