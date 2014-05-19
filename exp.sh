#!/bin/sh

#time  ./perforator.py -t 'func=reverse|num=1|time=360|pause=20' -o auto
#time  ./perforator.py -t 'func=reverse|num=10000|time=0.1|pause=0.1' -o auto
time ./perforator.py -t 'func=reverse|num=1000|time=0.1|pause=0.1' \
  -b sdag sdagp blosc wordpress -o "reverse_num=1000,pause=0.1,time=0.1_benches=sdag_sdagp_blosc_wordpress.pickle"

