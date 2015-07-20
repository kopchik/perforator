#!/usr/bin/env python3

from itertools import cycle
from libgui import *
import time
from sys import exit


@mywrapper
def gui():
  num_cores = 8
  bars = [Bar() for _ in range(8)]
  root = \
      Border(
        VList(
          HList(*bars),
          Border(
            Text(id='logwin'),
            label="Logs"),
          Input(),
          Button(cb=exit),
        ),

      )


 # loop(root)

  root.initroot()
  v = 0
  inpt = myinput(timeout=0.2)
  while True:
    v = (v + 0.1) % 1.5
    [bar.update(v) and time.sleep(0.7) for bar in bars]
    key = next(inpt)
    #root['logwin'].println(key)
    #time.sleep(0.1)


if __name__ == '__main__':
  gui()
