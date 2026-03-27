FROM ubuntu:22.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget unzip xvfb libxtst6 libxrender1 libxi6 \
    openjdk-11-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Download and install IB Gateway (stable version)
ARG IB_GATEWAY_VERSION=10.30.1t
RUN wget -q https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh -O /tmp/ibgateway-install.sh && \
    chmod +x /tmp/ibgateway-install.sh && \
    yes n | /tmp/ibgateway-install.sh && \
    rm /tmp/ibgateway-install.sh

# Copy IB Gateway config
COPY config.ini /root/Jts/config.ini
COPY run.sh /opt/run.sh
RUN chmod +x /opt/run.sh

EXPOSE 4001 4002 4003

CMD ["/opt/run.sh"]
