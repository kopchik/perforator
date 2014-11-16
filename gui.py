#!/usr/bin/env python3
from perf.qemu import NotCountedError
from curses import wrapper, newwin
from threading import Thread
from collections import defaultdict, deque
from queue import Queue
from curses import *
import time

"""
main screen
cmd on the bottom with history
"""


class Stat:
  def __init__(self):
    self.shared = deque(maxlen=10)
    self.isolated = deque(maxlen=10)


def mywrapper(f):
  return lambda *args, **kwargs: wrapper(f, *args, **kwargs)


class Win:
  def __init__(self, cwin, decor=True):
    self.cwin = cwin
    self.decor = decor
  def clear(self, color=None):
    self.cwin.clear()
    if self.decor:
      self.cwin.border()
    self.cwin.refresh()


class TopWin(Win):
  def __init__(self, *args, vms=[], **kwargs):
    super().__init__(*args, **kwargs)
    self.vms = vms
    self.vmstat = defaultdict(Stat)

    self.collector = Thread(target=collect, args=(self.vms, self.vmstat), kwargs={'cb':self.show})
    self.collector.daemon = True
    self.collector.start()

  def show(self):
    for i, vm in enumerate(self.vms):
      stat = self.vmstat[vm]
      self.cwin.addstr(i, 0, "XXX")


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
def top(scr, vms=[]):
  #scr.clear()
  max_y, max_x = scr.getmaxyx()
  topcwin = scr.derwin(len(vms)*2+2, max_x, 0, 0)
  top = TopWin(topcwin, vms=vms)
  #print(dir(scr))
  #print(vms)
  time.sleep(3)

from config import VMS as vms
top(vms=vms)
