#!/bin/sh

NUM=1000

for INTERVAL in 1 2 5 10; do
  sync
  ./qemu.py killall
  sleep 10
  ./perforator.py -t "func=distribution,num=$NUM,interval=$INTERVAL"  -o auto
  if [ $? -ne 0 ]; then
    exit 1
  fi
done
exit

for SUBINT in 1 2 5 10; do
  sync
  ./qemu.py killall
  sleep 10
#  ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=$SUBINT"  -o auto
  ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=50,subinterval=$SUBINT"   -o auto
  if [ $? -ne 0 ]; then
    echo "ACHTUNG, test terminated unsuccessfully"
    exit 1
  fi
  sleep 10
  ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=20,subinterval=$SUBINT"   -o auto
  if [ $? -ne 0 ]; then
    echo "ACHTUNG, test terminated unsuccessfully"
    exit 1
  fi
done
