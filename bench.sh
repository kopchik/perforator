#!/bin/bash

for x in `seq 30`; do
  ./profile.py 2>> ./results/profile
done
