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

# Base TM port
BASE_TM_PORT=8000

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

# Index to increment TM ports
index=0

# Loop over all arguments, skipping -t
for car_id in "$@"; do
    if [ "$car_id" = "-t" ]; then
        continue
    fi

    # Compute TM port for this car
    TM_PORT=$((BASE_TM_PORT + index))

     # Generate name string from index
    CAR_NAME="Car_$index"

    if [ "$USE_T" = true ]; then
        python ./one_car_route.py --read --id "$car_id" -t --tm-port "$TM_PORT" --name "$CAR_NAME" &
    else
        python ./one_car_route.py --read --id "$car_id" --tm-port "$TM_PORT" --name "$CAR_NAME" &
    fi

    # Save PID
    pids+=($!)

    # Increment index for next car
    index=$((index + 1))

done

# Wait for all background processes to finish
wait