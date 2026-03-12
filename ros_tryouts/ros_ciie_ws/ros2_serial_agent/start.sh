#!/bin/bash
source ../config/.env 
cd ros2_serial_agent/
sudo apt update && sudo apt install tmux
pip install pyserial
colcon build --packages-select ros2_serial_agent
tmux
source install/setup.bash
export BAUDRATE Y EL USB EIFEEPOD
ros2 run ros2_serial_agent serial_agent
tmux 2> curl iniorbit
tmux