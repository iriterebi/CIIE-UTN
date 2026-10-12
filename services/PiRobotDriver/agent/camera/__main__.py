import os

import rclpy
from dotenv import load_dotenv

from ..domain.publisher_info import TopicInfo
from . import CameraNode

_ = load_dotenv()

CAMERA_DEVICE = os.getenv("CAMERA_DEVICE", "/dev/video0")


with (
    rclpy.init(args=None),
    CameraNode(
        camera_device=CAMERA_DEVICE,
        publisher_info=TopicInfo(topic="usb_cam/image_raw", qos_profile=10)
    ) as node,
):
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
