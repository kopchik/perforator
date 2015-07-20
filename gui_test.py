#!/usr/bin/env python3

from itertools import cycle
from libgui import *
import time


if __name__ == '__main__':
  bars = []
  for i, color in zip(range(8), cycle([t.blue, t.green])):
    cpu = Bar(color=color)
    ipc = Bar(color=color)
    bars.append(cpu)
    bars.append(ipc)


  root = VList(*bars)
  #loop(root)
  root.initroot()
  root.canvas.clear()
  value = 0
  while True:
    value = (value + 0.01) % 1.5
    for bar in bars:
      bar.update(value)
    root.draw()
    time.sleep(0.01)
  #loop(root)

