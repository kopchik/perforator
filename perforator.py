#!/usr/bin/env python3
import pyximport; pyximport.install(pyimport = True)
from perflib import Task

from time import time, sleep
from psutil import process_iter
import math

PERIOD = 0.01
TIME = 0.1
TIMES = round(TIME/PERIOD)
THRESH = 10 # min CPU usage in %


def get_heavy_tasks(thr=THRESH, t=0.3):
	[p.cpu_percent() for p in process_iter()]
	sleep(t)
	## short version
	# return [p.pid for p in process_iter() if p.cpu_percent()>10]
	r = []
	for p in process_iter():
		cpu = p.cpu_percent()
		if cpu > 10:
			print("{pid:<7} {name:<12} {cpu}".format(pid=p.pid, name=p.name(), cpu=cpu))
			r.append(p.pid)
	return r


if __name__ == '__main__':
	pids = get_heavy_tasks()
	tasks = [Task(p) for p in pids]

	# for p in pids:
	t = Task(0)
	for x in range(4):
		print(t.measure(PERIOD))
