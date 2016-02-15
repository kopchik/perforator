#!/usr/bin/env python3

import tty
from sys import stdin
import os
import time
from select import select
from itertools import zip_longest

class ESC: pass
class UP: pass
class DOWN: pass
class LEFT: pass
class RIGHT: pass
class CTRLC: pass

def myinput(timeout=0):
  ESCSEQ = b'\x1b['
  tty.setraw(stdin.fileno())
  #stdout = os.fdopen(stdin.fileno(), 'wb', 0)
  special = False
  while True:
    rlist, wlist, xlist = select([stdin], [], [], 0)
    ch = os.read(stdin.fileno(), 1)
    ch = ch.decode()
    if ch == '\x1b':
      if special:
        yield ESC
      else:
        special = True
    elif ch == '[':
      if not special:
        yield ch
    else:
      if special:
        special = False
        if   ch == 'A': yield UP
        elif ch == 'B': yield DOWN
        elif ch == 'C': yield RIGHT
        elif ch == 'D': yield LEFT
      else:
        yield ch

if __name__ == '__main__':
    for ch in myinput():
      print(ch, repr(ch), end='\r\n')
      if ch == 'q':
        break
