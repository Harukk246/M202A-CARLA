#!/bin/bash

# --- Config ---
REMOTE_USER="wifi"
REMOTE_HOST="127.0.0.1"
REMOTE_PORT="2222"

REMOTE_PATH="/home/wifi/videos/"
LOCAL_PATH="$HOME/M202A-CARLA/scripts/videos/"

echo "password is wifi"

# --- Sync ---
rsync -avz -e "ssh -p ${REMOTE_PORT}" "${LOCAL_PATH}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

echo "Sync complete"
