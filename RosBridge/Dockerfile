FROM docker.io/library/ros:humble-ros-base-jammy

# Instalar rosbridge_suite
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-rosbridge-suite \
    && rm -rf /var/lib/apt/lists/*

# Workspace
WORKDIR /ros_bridge_ws

# Copiar launch y config
COPY launch/ launch/
COPY config/ config/

# Entrypoint: sourcear ROS + workspace
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
