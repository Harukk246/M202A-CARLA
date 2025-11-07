#!/bin/bash
ffplay -fflags nobuffer -flags low_delay -framedrop -probesize 32 -analyzeduration 0 \
  -i "udp://127.0.0.1:5000"

