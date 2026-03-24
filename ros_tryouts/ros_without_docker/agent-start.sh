#!/bin/bash

# Evitar diálogos interactivos que bloquean el script
export DEBIAN_FRONTEND=noninteractive
SESSION="ros_agent"

echo "🔍 Verificando instalación de ROS 2 Jazzy..."

# CORRECCIÓN 1: Verificar la carpeta de Jazzy, no Humble
if [ -d "/opt/ros/jazzy" ]; then
    echo "✅ ROS 2 Jazzy ya está instalado."
else
    echo "🛠️ Iniciando instalación limpia para Debian 12 (Bookworm)..."
    
    # 1. Configuración de Locale
    sudo apt update && sudo apt install locales -y
    sudo locale-gen en_US.UTF-8
    sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
    export LANG=en_US.UTF-8

    # 2. Limpieza y Repositorios
    sudo rm -f /etc/apt/sources.list.d/ros2.list
    sudo apt install software-properties-common curl -y
    # Nota: Debian no usa 'add-apt-repository universe' como Ubuntu, 
    # pero no hace daño si ya lo tienes.
    
    sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
    
    # CORRECCIÓN 2: Usar 'bookworm' y no 'jammy' para el repo
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu bookworm main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

    # 3. Instalación de ROS-BASE
    sudo apt update
    sudo NEEDRESTART_MODE=a apt install ros-jazzy-ros-base python3-rosdep tmux -y
fi

# 4. Inicialización de rosdep
if [ ! -f "/etc/ros/rosdep/sources.list.d/20-default.list" ]; then
    sudo rosdep init
fi
rosdep update

# CORRECCIÓN 3: Cambiar Humble por Jazzy en los archivos de configuración
for RC_FILE in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$RC_FILE" ] && ! grep -q "source /opt/ros/jazzy/setup.bash" "$RC_FILE"; then
        echo "source /opt/ros/jazzy/setup.bash" >> "$RC_FILE"
        echo "✅ Configuración de Jazzy añadida a $RC_FILE"
    fi
done

echo "🚀 Agente listo. Ejecutando tmux-setup si existe..."
# ./tmux-setup.sh

# tmux select-window -t $SESSION:0
if [ ! -d "/opt/inorbit-agent" ]; then
    curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh
fi
