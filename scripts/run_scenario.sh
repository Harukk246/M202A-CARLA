#!/bin/bash
scenario=$1
shift 1
python /home/erdos/workspace/scenario_runner/scenario_runner.py --scenario $scenario --output $@
