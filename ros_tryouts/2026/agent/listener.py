"""
Test/debug node. Subscribes to /inorbit/custom_command and writes commands to serial.
Use this to verify the command pipeline without running the full scraper.
Do not run alongside scraper.py — both open the same serial port.
"""
import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), 'serial_scraper', '.env'))

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))


class CommandListener(Node):
    def __init__(self):
        super().__init__('command_listener_node')
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        self.get_logger().info(f'Command listener started on {SERIAL_PORT} at {BAUD_RATE} baud')
        self.subscription = self.create_subscription(
            String,
            '/inorbit/custom_command',
            self.on_command,
            10,
        )

    def on_command(self, msg: String):
        command = msg.data.strip()
        self.get_logger().info(f'Received command: {command}')
        self.ser.write((command + '\n').encode('utf-8'))

    def destroy_node(self):
        # self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CommandListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
