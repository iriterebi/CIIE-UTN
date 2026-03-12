FROM ros:humble-ros-base-jammy

# Instalar rosbridge_suite y herramientas de build
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ros-humble-rosbridge-suite \
        python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Workspace
WORKDIR /ros_bridge_ws

# Copiar y compilar paquetes custom
COPY src/ src/
RUN . /opt/ros/humble/setup.sh && \
    colcon build --symlink-install

# Copiar launch y config
COPY launch/ launch/
COPY config/ config/

# Entrypoint: sourcear ROS + workspace
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
