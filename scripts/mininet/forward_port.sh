#!/bin/bash
socat -u UDP4-RECV:5000,bind=127.0.0.1,reuseaddr UDP4-SENDTO:10.0.0.1:5000
