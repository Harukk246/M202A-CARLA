#!/bin/bash
ip link set root-eth0 up
echo "if you see an error it is normal, the route has automatically been created by mininet"
ip route add 10.0.0.0/24 dev root-eth0
