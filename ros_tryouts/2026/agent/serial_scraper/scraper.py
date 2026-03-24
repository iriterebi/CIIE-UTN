import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
from dotenv import load_dotenv

load_dotenv()

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))


class SerialScraper(Node):
    def __init__(self):
        super().__init__('serial_scraper_node')
        self.publisher_ = self.create_publisher(String, '/inorbit/custom_data', 10)
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        self.get_logger().info(f'Serial scraper started on {SERIAL_PORT} at {BAUD_RATE} baud')
        self.timer = self.create_timer(0.1, self.read_serial)

    def read_serial(self):
        if self.ser.in_waiting > 0:
            raw = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if raw:
                msg = String()
                msg.data = f'data_dummy={raw}'
                self.publisher_.publish(msg)
                self.get_logger().info(f'Publishing: {msg.data}')

    def destroy_node(self):
        self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialScraper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
