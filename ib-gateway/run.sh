#!/bin/bash
set -e

# Start virtual display
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1
sleep 1

# Start VNC server (no password for local dev, access via noVNC in browser)
x11vnc -display :1 -forever -nopw -shared -rfbport 5900 &
sleep 1

# Start noVNC web client (accessible at http://localhost:5105)
websockify --web /usr/share/novnc 6080 localhost:5900 &
sleep 1

echo "==================================================="
echo " IB Gateway ready"
echo " Open http://localhost:5105 to log in"
echo "==================================================="

# Start IB Gateway directly (you log in via the noVNC browser UI)
/opt/ibgateway/ibgateway
