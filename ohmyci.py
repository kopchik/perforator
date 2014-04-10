#!/usr/bin/env python3

from useful.csv import Reader as CSVReader
from math import sqrt
import argparse
import os

from scipy.stats import sem, t
from scipy.stats import norm
import numpy as np
import pylab as p


def f2list(fname, freq):
  ts, ins = [], []
  with open(fname) as csvfile:
    t_prev = 0
    for t, i, _ in CSVReader(csvfile, type=(float,int,str), errors='ignore'):
      delta = t - t_prev
      t_prev = t
      ipc = i/delta/freq
      #if ipc <0.7: continue
      ts.append(t*1000)
      ins.append(ipc)
    return ts, ins


def ci_student(a, confidence=0.9):
    n = len(a)
    mean = np.mean(a)  # mean value
    se = sem(a)        # standart error
    print("se", se)
    h = se * t.ppf((1+confidence)/2, n-1)
    std  = np.std(y)
    avgerr = np.mean([abs(mean-datum) for datum in y])
    print("mean: {:.3f}, STD: {:.3f}, RSTD: {:.3%}, AVGERR: {:.3%} {:.3f}".format(mean, std, std/mean, avgerr/mean, se))

    return (2*h)/mean

def ci_student2(a, confidence=0.9):
  n = len(a)
  mean = np.mean(a)
  sn2 = sum((v - mean)**2 for v in a)/(n-1)
  sn = sqrt(sn2)/sqrt(n)
  print("sn", sn)
  A = t.ppf((1+confidence)/2, n-1)
  ci = 2*(A*sn)
  return ci/mean

def ci_sort(a, confidence):
  a = sorted(a)
  n = len(a)
  skip = int(n*(1-confidence)/2)
  interval = a[skip:-skip]
  mean = np.mean(a)
  return (interval[-1]-interval[0])/mean


def ci_norm(data, confidence):
  mean=np.mean(data)
  sigma = np.std(data)
  v1, v2 = norm.interval(confidence, loc=mean, scale=sigma)
  return v2-v1


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Calculate confidence interval')
  parser.add_argument('-p', '--prefix', default="/home/sources/limit-ci/")
  parser.add_argument('-t', '--test')
  parser.add_argument('-c', '--cpufreq', type=int, default=3800*(10**6), help="specify CPU freq")
  parser.add_argument('-m', '--mode', required=True, help="Mode of operation")
  parser.add_argument('-o', '--output', default=None)
  ci_g = parser.add_argument_group('ci', 'Confidence interval')
  ci_g.add_argument('-l', '--level', default=0.9, type=int, help="confedence level")
  hist = parser.add_argument_group('hist', 'Histogram')
  hist.add_argument('-b', '--bins', type=int, default=30, help="Number of bins on histogram")
  hist.add_argument('-i', '--intervals', type=int, nargs='+', default=[100], help="Select intervals to plot")
  hist.add_argument('-r', '--range', type=int, nargs='+', default=[], help="Select intervals to plot")
  args = parser.parse_args()
  print(args)


  fname_tpl = args.prefix+"/{i}/{test}"

  if args.mode == 'hist':
    for interval in args.intervals:
      fname = fname_tpl.format(i=interval, test=args.test)
      print("opening", fname)
      _,y = f2list(fname, args.cpufreq)
      ci_student(y)
      p.hist(y, bins=args.bins, alpha=0.7, normed=False, label="Interval %sms"%interval)
    p.gca().yaxis.set_major_formatter(p.FuncFormatter(lambda x, _: "%s%%"%x))

  elif args.mode == 'ci':
    #funcs = [ci_student, ci_sort, ci_norm]
    #funcs = [ci_student, ci_student2]
    funcs = [ci_student]
    results = [[] for f in funcs]
    if args.range:
      assert len(args.range) in [2,3], "--range accepts 2 or 3 arguments"
      if len(args.range) == 3:
        start, stop, step = args.range
      else:
        start, stop = args.range
        step = 1
      X = range(start, stop+1, step)
    else:
      entries = os.listdir(args.prefix)
      X = sorted(entries, key=int)
    for i in X:
      print(i)
      fname = fname_tpl.format(i=i, test=args.test)
      _,y = f2list(fname, args.cpufreq)
      for i,f in enumerate(funcs):
        mean = np.mean(y)
        results[i].append(f(y, 0.9)/mean*100)
    for f,r in zip(funcs,results):
      p.plot(X, r, 'o-', label=f.__name__)
    #p.rc('text', usetex=True)
    p.title(r"CI vs Time for %s"%args.test)
    p.xlabel('measurement duration, ms')
    p.ylabel('Relative Confidence Interval, %')
  elif args.mode == 'plot':
    p.title(r"Measurements for *%s* with intervals %sms"% (args.test, args.intervals))
    p.xlabel('Time, ms')
    p.ylabel('Instructions per cycle, IPC')
    for interval in args.intervals:
      fname = fname_tpl.format(i=interval, test=args.test)
      x,y = f2list(fname, args.cpufreq)
      ci_student(y)
      p.plot(x, y, 'o-', label="Interval %s" % interval)
  else:
    sys.exit("unknown operation mode %s" % args.mode)


  p.legend(loc='best')
  if args.output:
    p.savefig(args.output)
  else:
    p.show()
