#!/bin/bash
# THIS SCRIPT IS TO BE RUN INSIDE DOCKER

export XDG_RUNTIME_DIR=/tmp/runtime-$USER
mkdir -p $XDG_RUNTIME_DIR
chmod 700 $XDG_RUNTIME_DIR

# Run Carla simulator, passes all arguments to run_simulator.sh
/home/erdos/workspace/pylot/scripts/run_simulator.sh "$@" 
