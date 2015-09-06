#!/bin/bash

for x in `seq 100`; do
  ./profile.py 2>> ./results/profile_assign_by_ideal_perf
done
