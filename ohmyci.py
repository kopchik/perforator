#!/usr/bin/env python3

from useful.csv import Reader as CSVReader
import argparse

from scipy.stats import sem, t
import numpy as np
from scipy.stats import norm
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


def ci_student(a, confidence):
    n = len(a)
    mean = np.mean(a)  # mean value
    se = sem(a)        # standart error
    h = se * t.ppf((1+confidence)/2, n-1)
    return 2*h/mean


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
  args = parser.parse_args()
  print(args)


  fname_tpl = args.prefix+"/{i}/{test}"

  if args.mode == 'hist':
    for interval in args.intervals:
      fname = fname_tpl.format(i=interval, test=args.test)
      print("opening", fname)
      _,y = f2list(fname, args.cpufreq)
      mean = np.mean(y)
      std  = np.std(y)
      avgerr = np.mean([abs(mean-datum) for datum in y])
      print("mean: {:.3f}, STD: {:.3f}, RSTD: {:.3%}, AVGERR: {:.3%}".format(mean, std, std/mean, avgerr/mean))
      p.hist(y, bins=args.bins, alpha=0.7, normed=True, label="Interval %sms"%interval)
    p.legend(loc='best')

  elif args.mode == 'ci':
    #funcs = [ci_student, ci_sort, ci_norm]
    funcs = [ci_student]
    results = [[] for f in funcs]
    X = range(1,101)
    for i in X:
      fname = fname_tpl.format(i=i, test=args.test)
      _,y = f2list(fname, args.cpufreq)
      for i,f in enumerate(funcs):
        mean = np.mean(y)
        results[i].append(f(y, 0.9)/mean*100)
    for f,r in zip(funcs,results):
      p.plot(r, label=f.__name__)
    p.legend(loc='best')
    #p.rc('text', usetex=True)
    p.title(r"CI vs Time for %s"%args.test)
    p.xlabel('measurement duration, ms')
    p.ylabel('Relative Confidence Interval, %')
  elif args.mode == 'plot':
    fname = fname_tpl.format(i=args.interval, test=args.test)
    x,y = f2list(fname, args.cpufreq)
    p.plot(x,y)
    p.title(r"Measurements for *%s* with interval %s"% (args.test, args.interval))
    p.xlabel('Instructions per cycle, IPC')
    p.ylabel('Time, ms')
  else:
    sys.exit("unknown operation mode %s" % args.mode)

  if args.output:
    p.savefig(args.output)
  else:
    p.show()
