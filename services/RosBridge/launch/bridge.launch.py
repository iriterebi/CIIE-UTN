"""
Launch file para rosbridge_server.

Uso:
  ros2 launch /ros_bridge_ws/launch/bridge.launch.py
"""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=['/ros_bridge_ws/config/rosbridge_params.yaml'],
        output='screen',
    )

    return LaunchDescription([
        rosbridge_node,
    ])
