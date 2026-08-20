FROM osrf/ros:jazzy

WORKDIR /root/workspace

ENV container=docker
ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DOMAIN_ID=42
ENV PIP_BREAK_SYSTEM_PACKAGES=1


RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    python3-pip \
    python3-serial \
    sudo \
    tmux \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install python-dotenv virtualenv

# Make ROS available to all shells
RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc && \
    echo "export ROS_DOMAIN_ID=42" >> /root/.bashrc

RUN wget -O /root/inoribt-installer.sh  https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN && \
    chmod +x /root/inoribt-installer.sh

COPY ./tmux-start.sh /root/tmux-start.sh
RUN chmod +x /root/tmux-start.sh

COPY ./start.sh /root/start.sh
RUN chmod +x /root/start.sh

COPY .agent/ /root/agent/
COPY ./inorbit_configs/ /root/inorbit_configs/

# El ENTRYPOINT /ros_entrypoint.sh (heredado de ros:jazzy) sourcea /opt/ros/jazzy/setup.bash
# y ejecuta el CMD, dejando rclpy importable.
# CMD acá (no repetido en `final`): `final` extiende este stage y lo hereda tal
# cual, ya que continúa la misma lineage de filesystem (no hay COPY --from=).
CMD ["sh", "/root/start.sh"]
