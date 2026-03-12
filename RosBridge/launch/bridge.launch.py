"""
Launch file para rosbridge_server + nodo mock opcional.

Uso:
  ros2 launch /ros_bridge_ws/launch/bridge.launch.py              # solo rosbridge
  ros2 launch /ros_bridge_ws/launch/bridge.launch.py demo:=true   # rosbridge + mock
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    demo_arg = DeclareLaunchArgument(
        'demo',
        default_value='false',
        description='Lanzar nodo mock_robot para modo demo',
    )

    rosbridge_node = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=['/ros_bridge_ws/config/rosbridge_params.yaml'],
        output='screen',
    )

    mock_robot_node = Node(
        package='mock_robot',
        executable='mock_robot_node',
        name='mock_robot_node',
        output='screen',
        condition=IfCondition(LaunchConfiguration('demo')),
    )

    return LaunchDescription([
        demo_arg,
        rosbridge_node,
        mock_robot_node,
    ])
