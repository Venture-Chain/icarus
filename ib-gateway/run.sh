#!/bin/bash
# Start Xvfb for headless operation
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1

# Start IB Gateway
/opt/ibgateway/ibgateway
