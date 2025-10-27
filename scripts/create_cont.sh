#!/usr/bin/env bash
set -euo pipefail

# Let container talk to your X server (you already ran xhost on the host)
: "${DISPLAY:=${DISPLAY:-:0}}"

docker run -it --rm \
  --name pylot-carla \
  --gpus all \
  -e DISPLAY="$DISPLAY" \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e NVIDIA_DRIVER_CAPABILITIES=graphics,utility,compute \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
  -v "$HOME/carla-workspace":/workspace \
  -v /dev/snd:/dev/snd \
  -e PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native \
  -v ${XDG_RUNTIME_DIR}/pulse/native:${XDG_RUNTIME_DIR}/pulse/native \
  --group-add $(getent group audio | cut -d: -f3) \
  --network host \
  --privileged \
  erdosproject/pylot:latest \
  /bin/bash

