#!/bin/bash

# Check if -t was given anywhere in the arguments
USE_T=false
for arg in "$@"; do
    if [ "$arg" = "-t" ]; then
        USE_T=true
        break
    fi
done

# Loop over all arguments, skipping -t
for car_id in "$@"; do
    if [ "$car_id" = "-t" ]; then
        continue
    fi

    if [ "$USE_T" = true ]; then
        python ./one_car_route.py --read --id "$car_id" -t
    else
        python ./one_car_route.py --read --id "$car_id"
    fi
done