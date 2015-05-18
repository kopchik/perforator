#!/bin/bash

T=30
for bench in matrix wordpress blosc static sdag sdagp pgbench ffmpeg; do
  sync
  echo $bench
 ./perforator.py -t "func=syswide_stat,time=$T" -b $bench
 sleep 2
 ./perforator.py -t "func=syswide_stat,time=$T" -b $bench $bench $bench $bench $bench $bench $bench $bench
 echo "========="
done
