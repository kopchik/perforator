#!/bin/bash

#CMD="/home/sources/perftest/benches/test_SDAG/test_sdag+ -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat"
#CMD="/home/sources/perftest/benches/test_SDAG/test_sdag -t 5 -q 1000 /home/sources/perftest/benches/test_SDAG/dataset.dat"
#CMD="bencher.py -s 100000 -- ffmpeg -i /home/sources/avatar_trailer.m2ts \
#-strict -2 \
#-threads 1 -t 10 -y -strict -2 -loglevel panic \
#-acodec aac -aq 100 \
#-vcodec libx264 -preset fast -crf 22 \
#-f mp4 /dev/null"
CMD="/home/sources/perftest/benches/matrix.py -s 512 -r 100000"

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
