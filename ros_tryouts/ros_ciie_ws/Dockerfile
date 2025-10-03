FROM ros:humble-ros-base-jammy

# Dependencias de Python
RUN apt-get update && apt-get install -y \
    python3-pip python3-venv \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# Crear workspace
WORKDIR /ros_ciie_ws
RUN mkdir -p src

# Configuración de entorno
SHELL ["/bin/bash", "-c"]
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc \
 && echo "source /ros_ciie_ws/install/setup.bash" >> /root/.bashrc

CMD ["bash"]
