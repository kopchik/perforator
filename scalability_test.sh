#!/bin/bash

CMD="/home/sources/perftest/benches/test_SDAG/test_sdag+ -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat"
#CMD="/home/sources/perftest/benches/test_SDAG/test_sdag -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat"
OUTPUT="./scalability_results.txt"
TIME=60
rm $OUTPUT
for i in `seq 8`; do
  echo $i
  $CMD &
  sleep 1
  perf stat -a -o $OUTPUT --append sleep $TIME
done

# kill background tasks
jobs -p | xargs kill -9
