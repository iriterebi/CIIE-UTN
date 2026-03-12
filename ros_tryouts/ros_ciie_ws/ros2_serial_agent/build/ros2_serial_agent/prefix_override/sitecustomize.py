import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/ros_ciie_ws/ros2_serial_agent/install/ros2_serial_agent'
