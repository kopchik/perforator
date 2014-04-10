#!/usr/bin/env python3

from time import time, sleep
import gc; gc.disable()
import os


class Task:
  def __init__(self, pid):
    os.kill(pid, 0)  # check if process exists
    self.pid = pid
  def measure(self):
    


interval = 0.01
if __name__ == '__main__':
  for x in range(1000):
    t = -time()
    sleep(interval)
    t += time()
    prec = abs(1-interval/t)
    print(prec*100)
