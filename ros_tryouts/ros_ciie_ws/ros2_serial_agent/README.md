sourceconfig/.env *desde el root de docker*
cd ros2_serial_agent/
pip install pyserial
colcon build --packages-select ros2_serial_agent
source install/setup.bash
ros2 run ros2_serial_agent serial_agent