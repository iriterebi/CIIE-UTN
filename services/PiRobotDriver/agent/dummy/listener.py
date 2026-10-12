"""
Test/debug node. Subscribes to /inorbit/custom_command and writes commands to serial.
Use this to verify the command pipeline without running the full scraper.
Do not run alongside scraper.py — both open the same serial port.
"""

from rclpy.node import Node
from std_msgs.msg import String

from ..domain.publisher_info import TopicInfo


class CommandListener(Node):

    def __init__(self, topic_info: TopicInfo):
        super().__init__('command_listener_node')

        self.subscription = self.create_subscription(
            String,
            topic_info.topic,
            self.on_command,
            topic_info.qos_profile,
        )

    def on_command(self, msg: String):
        command = msg.data.strip()
        _ = self.get_logger().info(f'Received command: {command}')
