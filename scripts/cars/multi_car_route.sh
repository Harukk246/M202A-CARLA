#!/bin/bash

# Check if -t was given anywhere in the arguments
USE_T=false
for arg in "$@"; do
    if [ "$arg" = "-t" ]; then
        USE_T=true
        break
    fi
done

# Array to store PIDs
pids=()

# Function to cleanup background processes on Ctrl+C
cleanup() {
    echo "Stopping all cars..."
    for pid in "${pids[@]}"; do
        kill "$pid" 2>/dev/null
    done
    exit
}

# Trap Ctrl+C
trap cleanup SIGINT

# Loop over all arguments, skipping -t
for car_id in "$@"; do
    if [ "$car_id" = "-t" ]; then
        continue
    fi

    if [ "$USE_T" = true ]; then
        python ./one_car_route.py --read --id "$car_id" -t &
    else
        python ./one_car_route.py --read --id "$car_id" &
    fi

    # Save PID
    pids+=($!)

    sleep(3)  # slight delay to stagger startups
done

# Wait for all background processes to finish
wait