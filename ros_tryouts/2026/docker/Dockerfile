# Usamos la imagen oficial más liviana de ROS 2 Humble (basada en Ubuntu 22.04)
FROM ros:humble-ros-core-jammy

# Evitar preguntas interactivas durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# 1. Instalar dependencias mínimas de sistema y Python para Serial
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    ca-certificates \
    net-tools \
    iputils-ping \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-serial \
    virtualenv \
    gcc \
    build-essential \
    sudo \
    curl \
    udev \
    tmux \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_BREAK_SYSTEM_PACKAGES=1
ENV ROS_DOMAIN_ID=42

# These ROS env vars are set by the base image entrypoint at runtime, but are
# NOT available during docker build RUN steps unless explicitly declared here.
# The InOrbit installer needs them to detect the ROS version correctly.
ENV ROS_DISTRO=humble
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2

# 2. Instalar agente InOrbit
# The installer has interactive prompts that read from /dev/tty which fail in Docker.
# We download the script, patch out the tty reads, then run it.
# systemctl steps will fail in Docker but the binary is still installed.
RUN curl -fsSL https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN -o /tmp/inorbit_install.sh \
    && sed -i 's|read -r input </dev/tty|: # skip interactive read|g' /tmp/inorbit_install.sh \
    && sh /tmp/inorbit_install.sh || true \
    && rm -f /tmp/inorbit_install.sh

# 3. Configurar el entorno de ROS 2 para que cargue automáticamente
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Copiar script de inicio de tmux
COPY ros_tryouts/2026/tmux-start.sh /root/tmux-start.sh
RUN chmod +x /root/tmux-start.sh

# Configurar el directorio de trabajo
WORKDIR /root/workspace

CMD ["/root/tmux-start.sh"]