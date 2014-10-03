#!/bin/bash

for x in `seq 10`; do
  ./profile.py | grep "improvement:" 2>> ./results/profile
done
