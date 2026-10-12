import os

import rclpy
from dotenv import load_dotenv

from ..domain.publisher_info import TopicInfo
from . import SerialScraper

_ = load_dotenv()

SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))

with (
    rclpy.init(args=None),
    SerialScraper(
        serial_port=SERIAL_PORT,
        baud_rate=BAUD_RATE,
        publisher_info=TopicInfo("/inorbit/custom_data", 10),
        subscription_info=TopicInfo("/inorbit/custom_command", 10),
    ) as node,
):
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
