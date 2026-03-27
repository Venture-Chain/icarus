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
echo " IB Gateway starting..."
echo " noVNC: http://localhost:5105  (approve 2FA here)"
echo " VNC:   localhost:5900"
echo "==================================================="

# Write IBC credentials from env vars
if [ -n "$TWS_USERID" ] && [ -n "$TWS_PASSWORD" ]; then
    sed -i "s/^IbLoginId=.*/IbLoginId=$TWS_USERID/" /opt/ibc/ibc.ini
    sed -i "s/^IbPassword=.*/IbPassword=$TWS_PASSWORD/" /opt/ibc/ibc.ini
    sed -i "s/^TradingMode=.*/TradingMode=${TRADING_MODE:-paper}/" /opt/ibc/ibc.ini
fi

# Start IB Gateway via IBC (handles login automation and 2FA waiting)
/opt/ibc/gatewaystart.sh -inline
