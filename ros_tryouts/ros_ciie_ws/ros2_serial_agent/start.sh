#!/bin/bash
source /config/.env 
cd ros2_serial_agent/
sudo apt update && sudo apt install -y tmux
pip install pyserial

echo "Compilando ros2_serial_agent..."
colcon build --packages-select ros2_serial_agent


SOURCE_COMMAND="source install/setup.bash"

# --- PASO 2: Gestión de la Sesión TMUX ---

# Nombre de la sesión
SESSION="ros_agent_session"

# Elimina cualquier sesión existente con el mismo nombre
tmux kill-session -t $SESSION 2>/dev/null

# 6. Inicia una nueva sesión de tmux
tmux new-session -d -s $SESSION

# --- Ventana 1: ROS 2 Agent ---

# Crea la primera ventana (automáticamente es index 0) y le pone nombre
tmux rename-window -t $SESSION:0 "ROS_Agent"

# Envía los comandos para la Ventana 1 (el agente serial)
# El comando 'send-keys' ejecuta la preparación y el proceso
tmux send-keys -t $SESSION:0 "$SOURCE_COMMAND" C-m
tmux send-keys -t $SESSION:0 "ros2 run ros2_serial_agent serial_agent" C-m

# --- Ventana 2: Cliente de Prueba (Curl) ---

# 7. Crea una nueva ventana (simula tu 'tmux 2>')
tmux new-window -t $SESSION:1 -n "Curl_Test"


tmux new-window -t $SESSION:2 -n "Agent Interaction"


tmux attach-session -t $SESSION