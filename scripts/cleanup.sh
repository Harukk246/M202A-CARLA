#!/bin/bash
# Stops any running CARLA processes safely

# Find CARLA UE4 process
CARLA_PIDS=$(pgrep -f "CarlaUE4-Linux-Shipping")

if [ -z "$CARLA_PIDS" ]; then
    echo "No running CARLA processes found."
    exit 0
fi

echo "Found CARLA processes: $CARLA_PIDS"
echo "Sending SIGTERM to allow graceful shutdown..."
kill $CARLA_PIDS

# Wait up to 10 seconds for processes to exit
for i in {1..10}; do
    sleep 1
    STILL_RUNNING=$(pgrep -f "CarlaUE4-Linux-Shipping")
    if [ -z "$STILL_RUNNING" ]; then
        echo "CARLA stopped successfully."
        exit 0
    fi
    echo "Waiting for CARLA to exit..."
done

# If still running, force kill
echo "CARLA did not stop in time. Sending SIGKILL..."
kill -9 $CARLA_PIDS

echo "Cleanup complete."
