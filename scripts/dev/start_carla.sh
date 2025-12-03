#!/bin/bash
if [ -z "$CARLA_ENV_LOADED" ]; then
    echo "setting up environment"
    export CARLA_ROOT=$HOME/workspace/pylot/dependencies/CARLA_0.9.10.1/
    export PYLOT_HOME=$HOME/workspace/pylot
    export SCENARIO_RUNNER_ROOT=$HOME/workspace/scenario_runner

    export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.10-py3.7-linux-x86_64.egg
    export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/agents/navigation/
    export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
    export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI
   
    export PYTHONPATH=$PYTHONPATH:$HOME/workspace/M202A-CARLA/scripts

    export XDG_RUNTIME_DIR=/tmp/runtime-$USER
    mkdir -p $XDG_RUNTIME_DIR
    chmod 700 $XDG_RUNTIME_DIR

    # mark setup as done
    export CARLA_ENV_LOADED=1
fi

# Check if Carla is already running
if pgrep -f "CarlaUE4" > /dev/null; then
    echo "CARLA is already running. Skipping simulator launch."
else
    echo "Starting CARLA simulator..."
    ./run_simulator.sh "$@" &
    sleep 5
fi

python load_town5.py
