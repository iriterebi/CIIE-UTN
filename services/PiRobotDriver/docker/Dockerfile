FROM osrf/ros:jazzy-desktop

ENV container=docker
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DOMAIN_ID=42
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# HTTP apt traffic is blocked at the network level; switch to HTTPS to bypass
RUN find /etc/apt/ -name '*.list' -o -name '*.sources' | \
    xargs sed -i \
        -e 's|http://archive.ubuntu.com|https://archive.ubuntu.com|g' \
        -e 's|http://security.ubuntu.com|https://security.ubuntu.com|g' \
        -e 's|http://packages.ros.org|https://packages.ros.org|g' \
    2>/dev/null; true

# Clean up systemd units that don't apply in containers
RUN find /etc/systemd/system /usr/lib/systemd/system \
    -path '*.wants/*' \
    -not -name '*journald*' \
    -not -name '*systemd-tmpfiles*' \
    -not -name '*systemd-user-sessions*' \
    -exec rm -f {} \; 2>/dev/null || true

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    python3-pip \
    python3-serial \
    sudo \
    tmux \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install python-dotenv virtualenv

# Make ROS available to all shells
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc && \
    echo "export ROS_DOMAIN_ID=42" >> /root/.bashrc

COPY ros_tryouts/2026/tmux-start.sh /root/tmux-start.sh
RUN chmod +x /root/tmux-start.sh

WORKDIR /root/workspace

CMD ["/sbin/init"]
