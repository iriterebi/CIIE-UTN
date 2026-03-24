#!/bin/bash
SESSION="ros_agent"

# Comprobar si ros2 ya está instalado viendo si existe la carpeta de Humble
if [ -d "/opt/ros/humble" ]; then
    echo "✅ ROS 2 Humble ya está instalado en /opt/ros/humble."
    exit 0
else
    # 1. Configuración de Locale
    sudo apt update && sudo apt install locales -y
    sudo locale-gen en_US en_US.UTF-8
    sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
    export LANG=en_US.UTF-8

    # 2. Repositorios y Llaves
    sudo apt install software-properties-common curl -y
    sudo add-apt-repository universe -y
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

    # 3. Instalación de ROS-BASE (Sin GUI/RViz)
    sudo apt update
    sudo NEEDRESTART_MODE=a apt install ros-humble-ros-base python3-rosdep -y
fi

# 4. Inicialización de rosdep
if [ ! -f "/etc/ros/rosdep/sources.list.d/20-default.list" ]; then
    sudo rosdep init
fi
rosdep update

# 5. Configuración del entorno
if ! grep -q "source /opt/ros/humble/setup.bash" ~/.bashrc; then
    echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
    sudo apt install tmux -y
    echo "✅ Entorno configurado en .bashrc"
fi
echo "🚀 Agente listo"
source ~/.bashrc
./tmux-setup.sh

tmux select-window -t $SESSION:0
curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh