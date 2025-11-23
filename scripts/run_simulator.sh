#!/bin/bash                                                                                               │
                                                                                                          │
if [ -z "$CARLA_ROOT" ]; then                                                                             │
    echo "Please set \$CARLA_ROOT before running this script"                                             │
    exit 1                                                                                                │
fi                                                                                                        │
                                                                                                          │
if [ -z "$1" ]; then                                                                                      │
    PORT=2000                                                                                             │
else                                                                                                      │
    PORT=$1                                                                                               │
fi                                                                                                        │
                                                                                                          │
export SDL_AUDIODRIVER=dummy                                                                              │
${CARLA_ROOT}/CarlaUE4.sh -opengl -windowed -ResX=1800 -ResY=2400 -world-port=$PORT -benchmark -fps=20 -quality-level=Epic
