FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    wget unzip xvfb libxtst6 libxrender1 libxi6 \
    x11vnc novnc websockify && \
    ln -sf /usr/share/novnc/vnc.html /usr/share/novnc/index.html && \
    rm -rf /var/lib/apt/lists/*

# Install Azul Zulu JRE+FX 17.0.10 (JavaFX required by IB Gateway 10.37+)
RUN mkdir -p /opt/i4j_jres/Oda-jK0QgTEmVssfllLP && \
    wget -q https://cdn.azul.com/zulu/bin/zulu17.48.15-ca-fx-jre17.0.10-linux_x64.tar.gz -O /tmp/zulu-jre.tar.gz && \
    tar xzf /tmp/zulu-jre.tar.gz -C /opt/i4j_jres/Oda-jK0QgTEmVssfllLP && \
    mv /opt/i4j_jres/Oda-jK0QgTEmVssfllLP/zulu17.48.15-ca-fx-jre17.0.10-linux_x64 /opt/i4j_jres/Oda-jK0QgTEmVssfllLP/17.0.10.0.101-zulu && \
    rm /tmp/zulu-jre.tar.gz

ENV INSTALL4J_JAVA_HOME=/opt/i4j_jres/Oda-jK0QgTEmVssfllLP/17.0.10.0.101-zulu

# Download and install IB Gateway (stable standalone)
RUN wget -q https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh -O /tmp/ibgateway-install.sh && \
    chmod +x /tmp/ibgateway-install.sh && \
    /tmp/ibgateway-install.sh -q -dir /opt/ibgateway && \
    rm /tmp/ibgateway-install.sh

# Copy configs
COPY config.ini /root/Jts/config.ini
COPY run.sh /opt/run.sh
RUN chmod +x /opt/run.sh

# 4003 = IB API, 5900 = VNC, 6080 = noVNC web
EXPOSE 4003 5900 6080

CMD ["/opt/run.sh"]
