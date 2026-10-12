"""
Camera node. Captures frames from a USB camera at ~30 fps and publishes them
to usb_cam/image_raw as ROS sensor_msgs/Image messages.
"""

from typing import override

import cv2
from rclpy.node import Node
from rclpy.publisher import Publisher
from rclpy.timer import Timer
from sensor_msgs.msg import Image

from ..domain.publisher_info import TopicInfo


class CameraNode(Node):
    def __init__(self, *, camera_device: str, publisher_info: TopicInfo):
        super().__init__("camera_node")
        self.publisher_: Publisher[Image] = self.create_publisher(
            Image, publisher_info.topic, publisher_info.qos_profile
        )

        device_index = self._device_index(camera_device)
        self.cap: cv2.VideoCapture = cv2.VideoCapture(device_index)

        if not self.cap.isOpened():
            _ = self.get_logger().error(f"Could not open camera at {camera_device}")
            raise RuntimeError(f"Camera not available: {camera_device}")

        _ = self.get_logger().info(f"Camera node started on {camera_device}")

        self.timer: Timer = self.create_timer(0.033, self.publish_frame)  # ~30 fps

    def _device_index(self, device_path: str) -> int:
        try:
            return int(device_path.replace("/dev/video", ""))
        except ValueError:
            return 0

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            _ = self.get_logger().warning("Failed to capture frame")
            return
        h, w, _ = frame.shape
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.height = h
        msg.width = w
        msg.encoding = "bgr8"
        msg.is_bigendian = False
        msg.step = w * 3
        msg.data = frame.tobytes()
        self.publisher_.publish(msg)

    @override
    def destroy_node(self):
        self.cap.release()
        super().destroy_node()
