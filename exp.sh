#!/bin/sh

#time  ./perforator.py -t 'func=reverse|num=1|time=360|pause=20' -o auto
#time  ./perforator.py -t 'func=reverse|num=10000|time=0.1|pause=0.1' -o auto

#time ./perforator.py -t 'func=reverse|num=1|time=360|pause=20' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=1,pause=20,time=360_benches=sdag_sdagp_blosc_wordpress.pickle"
#time ./perforator.py -t 'func=reverse|num=1000|time=0.1|pause=0.1' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=1000,pause=0.1,time=0.1_benches=sdag_sdagp_blosc_wordpress.pickle"


#time ./perforator.py -t 'func=reverse|num=10000|time=0.1|pause=0.1' \
#  -b sdag sdagp blosc wordpress -o "results/reverse_num=10000,pause=0.1,time=0.1_benches=sdag_sdagp_blosc_wordpress.pickle"


#./perforator.py -t 'func=distribution|num=1000|interval=0.1' -o auto
#./perforator.py -t 'func=distribution|num=1000|interval=0.05' -o auto
#./perforator.py -t 'func=distribution|num=1000|interval=0.02' -o auto
#./perforator.py -t 'func=distribution|num=1000|interval=0.01' -o auto

#time ./perforator.py -t 'func=reverse_interference|num=1000|time=0.1|real_time=360' -o auto
#time ./perforator.py -t 'func=reverse|num=100|time=0.1' -o auto
#time ./perforator.py -t 'func=reverse|num=1000|time=0.2' -o auto
#time ./perforator.py -t 'func=reverse|num=1000|time=0.3' -o auto

#./perforator.py -t 'func=shared|num=1000|interval=0.1' -o auto
#sleep 60
#./perforator.py -t 'func=shared|num=1000|interval=0.05' -o auto
#sleep 60
#./perforator.py -t 'func=shared|num=1000|interval=0.02' -o auto
#sleep 60
#./perforator.py -t 'func=shared|num=1000|interval=0.01' -o auto
#sleep 60
#./perforator.py -t 'func=shared|num=1000|interval=0.005' -o auto
#sleep 60
#./perforator.py -t 'func=shared|num=10000|interval=0.001|pause=0.001' -o auto

#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.1|rate=100|skip=1" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.1|rate=200|skip=2" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.05|rate=200|skip=1" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.05|rate=200|skip=1" -o auto
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.05|rate=200|skip=2" -o auto
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.05|rate=200|skip=3" -o auto
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.1|rate=500|skip=1" -o auto; sleep 60
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.1|rate=500|skip=2" -o auto; sleep 60
#./perforator.py -t "func=distr_subsampling|num=300|interval=0.1|rate=500|skip=3" -o auto; sleep 60

#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.05|rate=500|skip=1" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.05|rate=500|skip=2" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.05|rate=500|skip=3" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.02|rate=500|skip=1" -o auto
#sleep 60
#./perforator.py -t "func=distr_subsampling|num=1000|interval=0.02|rate=500|skip=2" -o auto
#sleep 60

NUM=100

./perforator.py -t "func=distribution,num=$NUM,interval=10"  -o auto
sleep 20
./perforator.py -t "func=distribution,num=$NUM,interval=20"  -o auto
sleep 20
./perforator.py -t "func=distribution,num=$NUM,interval=50"  -o auto
sleep 20
./perforator.py -t "func=distribution,num=$NUM,interval=100"  -o auto
sleep 20
./perforator.py -t "func=distribution,num=$NUM,interval=200"  -o auto

time ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=1"  -o auto
sleep 20
time ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=2"  -o auto
sleep 20
time ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=5"  -o auto
sleep 20
time ./perforator.py -t "func=distribution_with_subsampling,num=$NUM,interval=100,subinterval=10"  -o auto
