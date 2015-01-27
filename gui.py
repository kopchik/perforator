#!/usr/bin/env python3

from perf.qemu import NotCountedError
from threading import Thread
from collections import defaultdict, deque
# from queue import Queue
import time
import sys
from libgui import Border, Bars, Button, Canvas, XY, Text, CMDInput, VList, mywrapper
import curses
from config import VMS

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
  # setup canvas
  size_y, size_x = scr.getmaxyx()
  size = XY(size_x, size_y)
  canvas = Canvas(scr, size)
  canvas.clear()

  # widget hierarchy
  root = \
      Border(
          VList(
              Border(
                  Bars([0.01, 0.5, 0.7, 1])),
              Border(
                  Text(id='logwin'),
                  label="Logs"),
              CMDInput(id='cmdinpt'),
              Button("QUIT", cb=sys.exit)),
          label="Per-Core Performane")

  # setup callbacks
  logwin = root['logwin']
  def cb(s):
    tstamp = time.strftime("%H:%M:%S", time.localtime())
    logwin.println("{} {}".format(tstamp, s))
    if s == 'quit':
      sys.exit()
  root['cmdinpt'].cb = cb

  # calculate widget placement and draw widgets
  root.init(pos=XY(0, 0), maxsize=size, canvas=canvas)
  root.setup_sigwinch()
  root.draw()

  # top-like bars
  vmstat = defaultdict(Stat)
  collector = Thread(target=collect,
                      args=(VMS, vmstat),
                      # kwargs={'cb':self.show}
                      )
  collector.daemon = True
  collector.start()


  # main loop
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