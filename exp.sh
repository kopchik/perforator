#!/bin/sh

NUM=1000

for INTERVAL in 10 20 50 100 200; do
  sync
  ./qemu.py killall
  sleep 10
  time ./perforator.py -t "func=distribution,num=$NUM,interval=$INTERVAL"  -o auto
  if [ $? -ne 0 ]; then
    exit 1
  fi
done

for SUBINT in 1 2 5 10; do
  sync
  ./qemu.py killall
  sleep 10
  time ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=$SUBINT"  -o auto
  if [ $? -ne 0 ]; then
    exit 1
  fi
done
