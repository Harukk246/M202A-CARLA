#!/bin/bash
export CARLA_ROOT=$HOME/workspace/carla
export PYLOT_HOME=$HOME/workspace/pylot
export SCENARIO_RUNNER_ROOT=$HOME/workspace/scenario_runner
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/dist/carla-0.9.10-py3.7-linux-x86_64.egg
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla/agents/navigation/
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI/carla
export PYTHONPATH=$PYTHONPATH:${CARLA_ROOT}/PythonAPI

