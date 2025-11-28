#!/bin/bash

# --- Config ---
REMOTE_USER="wifi"
REMOTE_HOST="127.0.0.1"
REMOTE_PORT="2222"

REMOTE_PATH="/home/wifi/M202A-CARLA/scripts/mininet/"
LOCAL_PATH="$HOME/M202A-CARLA/scripts/mininet/"

echo "password is wifi"

# --- Sync ---
rsync -avz -e "ssh -p ${REMOTE_PORT}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}" "${LOCAL_PATH}"

echo "Sync complete"
