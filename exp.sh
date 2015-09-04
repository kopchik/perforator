#!/bin/sh

#VMPID=
#perf kvm stat -p $VMPID -I 1000 -e instructions,cycles -x, -o sleep 30m

time ./perforator.py -t "func=real_loosers"
echo
echo ">>>>>>>>>>>>>>>><<<<<<<<<<<<<<<<"
echo
time ./perforator.py -t "func=loosers,num=1000,interval=10,pause=0.1"
exit

NUM=1000
INTINT=50

<<<<<<< HEAD
#for INTERVAL in 5 10 20 50 100 200; do
#for INTERVAL in 10 50 100; do
=======
>>>>>>> dd531c3663773139994aea40b8c6c88be7435c92
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

exit

#for SUBINT in 1 2 5 10; do
for SUBINT in 2 5; do
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
