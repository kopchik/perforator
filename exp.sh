#!/bin/sh

#time  ./perforator.py -t 'func=reverse|num=1|time=360|pause=20' -o auto
#time  ./perforator.py -t 'func=reverse|num=10000|time=0.1|pause=0.1' -o auto

#time ./perforator.py -t 'func=reverse|num=1|time=360|pause=20' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=1,pause=20,time=360_benches=sdag_sdagp_blosc_wordpress.pickle"
#time ./perforator.py -t 'func=reverse|num=1000|time=0.1|pause=0.1' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=1000,pause=0.1,time=0.1_benches=sdag_sdagp_blosc_wordpress.pickle"


#time ./perforator.py -t 'func=reverse|num=10000|time=0.1|pause=0.1' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=10000,pause=0.1,time=0.1_benches=sdag_sdagp_blosc_wordpress.pickle"


time python -m pdb ./perforator.py -t 'func=distribution|num=1000|interval=0.1' -o auto
time python -m pdb ./perforator.py -t 'func=distribution|num=1000|interval=0.05' -o auto
time python -m pdb ./perforator.py -t 'func=distribution|num=1000|interval=0.02' -o auto
time python -m pdb ./perforator.py -t 'func=distribution|num=1000|interval=0.01' -o auto

#time ./perforator.py -t 'func=reverse_interference|num=1000|time=0.1|real_time=360' -o auto
#time ./perforator.py -t 'func=reverse|num=100|time=0.1' -o auto
#time ./perforator.py -t 'func=reverse|num=1000|time=0.2' -o auto
#time ./perforator.py -t 'func=reverse|num=1000|time=0.3' -o auto
