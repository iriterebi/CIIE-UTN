# Usamos la imagen oficial más liviana de ROS 2 Humble (basada en Ubuntu 22.04)
FROM ros:humble-ros-core-jammy

# Evitar preguntas interactivas durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# 1. Instalar dependencias mínimas de sistema y Python para Serial
RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    iputils-ping \
    python3-pip \
    python3-serial \
    curl \
    udev \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar el agente de InOrbit (El comando curl de tu consola)
# REEMPLAZA 'TU_API_KEY_AQUI' por tu clave real
RUN curl -sSL https://install.inorbit.ai/TU_API_KEY_AQUI | sh

# 3. Configurar el entorno de ROS 2 para que cargue automáticamente
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Configurar el directorio de trabajo
WORKDIR /root/workspace

# Comando por defecto al iniciar el contenedor (mantiene el contenedor vivo)
CMD ["bash"]