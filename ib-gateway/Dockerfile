FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget unzip xvfb libxtst6 libxrender1 libxi6 \
    openjdk-11-jre-headless \
    x11vnc novnc websockify && \
    rm -rf /var/lib/apt/lists/*

# Download and install IB Gateway (stable version)
ARG IB_GATEWAY_VERSION=10.30.1t
RUN wget -q https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh -O /tmp/ibgateway-install.sh && \
    chmod +x /tmp/ibgateway-install.sh && \
    yes n | /tmp/ibgateway-install.sh && \
    rm /tmp/ibgateway-install.sh

# Copy configs
COPY config.ini /root/Jts/config.ini
COPY run.sh /opt/run.sh
RUN chmod +x /opt/run.sh

# 4003 = IB API, 5900 = VNC, 6080 = noVNC web
EXPOSE 4003 5900 6080

CMD ["/opt/run.sh"]
