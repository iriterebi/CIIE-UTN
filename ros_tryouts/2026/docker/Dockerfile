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
    systemd \
    systemd-sysv \
    dbus \
    && locale-gen en_US.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Clean up systemd units that don't apply in containers
RUN find /lib/systemd/system/sysinit.target.wants/ -not -name 'systemd-tmpfiles-setup.service' -delete \
    && rm -f /lib/systemd/system/multi-user.target.wants/* \
    && rm -f /etc/systemd/system/*.wants/* \
    && rm -f /lib/systemd/system/local-fs.target.wants/* \
    && rm -f /lib/systemd/system/sockets.target.wants/*udev* \
    && rm -f /lib/systemd/system/sockets.target.wants/*initctl* \
    && rm -f /lib/systemd/system/basic.target.wants/* \
    && rm -f /lib/systemd/system/anaconda.target.wants/*

ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN pip3 install python-dotenv opencv-python-headless
ENV ROS_DOMAIN_ID=42

# These ROS env vars are set by the base image entrypoint at runtime, but are
# NOT available during docker build RUN steps unless explicitly declared here.
# The InOrbit installer needs them to detect the ROS version correctly.
ENV ROS_DISTRO=humble
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2

# 2. Instalar agente InOrbit
#LOCALDEV
# RUN sudo curl -fsSL http://localdev.com:3000/liftoff/DuGMg5qt0DV9OAZc | sh -o /tmp/inorbit_install.sh \
#     && chmod +x /tmp/inorbit_install.sh \
#     && /tmp/inorbit_install.sh --no-systemd --no-sudo || true \
#     && rm -f /tmp/inorbit_install.sh

RUN curl -fsSL https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN -o /tmp/inorbit_install.sh \
    && sed -i 's|read -r input </dev/tty|: # skip interactive read|g' /tmp/inorbit_install.sh \
    && sh /tmp/inorbit_install.sh || true \
    && rm -f /tmp/inorbit_install.sh

# 3. Create systemd service unit for InOrbit
RUN printf '[Unit]\nDescription=InOrbit Agent\nAfter=network.target\n\n[Service]\nType=simple\nExecStart=/root/.inorbit/dist/scripts/start.sh\nRestart=on-failure\nUser=root\nEnvironment=ROS_DISTRO=humble\nEnvironment=ROS_PYTHON_VERSION=3\nEnvironment=ROS_VERSION=2\nEnvironment=ROS_DOMAIN_ID=42\n\n[Install]\nWantedBy=multi-user.target\n' \
    > /etc/systemd/system/inorbit.service \
    && systemctl enable inorbit || true

# 4. Configurar el entorno de ROS 2 para que cargue automáticamente
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Copiar script de inicio de tmux
COPY ros_tryouts/2026/tmux-start.sh /root/tmux-start.sh
RUN chmod +x /root/tmux-start.sh

# Configurar el directorio de trabajo
WORKDIR /root/workspace

CMD ["/lib/systemd/systemd"]
