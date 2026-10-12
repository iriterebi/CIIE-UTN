import os
from contextlib import ExitStack
from typing import Literal

import rclpy
from dotenv import load_dotenv
from rclpy.executors import MultiThreadedExecutor
from tap import Tap

from .camera import CameraNode
from .domain.publisher_info import TopicInfo
from .dummy import DummyListener, DummyPublisher
from .serial_scraper import SerialScraper

_ = load_dotenv()

CAMERA_DEVICE = os.getenv("CAMERA_DEVICE", "/dev/video0")
SERIAL_PORT = os.getenv("SERIAL_PORT", "/dev/ttyUSB0")
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))
CAMERA_PUBLISH_TOPIC = os.getenv("CAMERA_PUBLISH_TOPIC", "/usb_cam/image_raw")
SERIAL_PUBLISH_TOPIC = os.getenv("SERIAL_PUBLISH_TOPIC", "/inorbit/custom_data")
SERIAL_SUBSCRIPTION_TOPIC = os.getenv(
    "SERIAL_SUBSCRIPTION_TOPIC", "/inorbit/custom_command"
)


class MainArguments(Tap):
    camera: bool = False  # Enable Camera
    robot_type: Literal["serial", "dummy"] = "serial"  # comunication type


args = MainArguments().parse_args()

print(args)


with (
    rclpy.init(args=None),
    ExitStack() as stack,
    MultiThreadedExecutor(3) as executor,
):
    if args.camera:
        cameraNode = CameraNode(
            camera_device=CAMERA_DEVICE,
            publisher_info=TopicInfo(topic=CAMERA_PUBLISH_TOPIC, qos_profile=10),
        )
        _ = stack.push(cameraNode)
        _ = executor.add_node(cameraNode)

    match args.robot_type:
        case "serial":
            serialNode = SerialScraper(
                serial_port=SERIAL_PORT,
                baud_rate=BAUD_RATE,
                publisher_info=TopicInfo(topic=SERIAL_PUBLISH_TOPIC, qos_profile=10),
                subscription_info=TopicInfo(
                    topic=SERIAL_SUBSCRIPTION_TOPIC, qos_profile=10
                ),
            )
            _ = stack.push(serialNode)
            _ = executor.add_node(serialNode)

        case "dummy":
            _ = executor.add_node(
                stack.push(
                    DummyListener(
                        TopicInfo(topic=SERIAL_SUBSCRIPTION_TOPIC, qos_profile=10)
                    )
                )
            )
            _ = executor.add_node(
                stack.push(
                    DummyPublisher(
                        TopicInfo(topic=SERIAL_PUBLISH_TOPIC, qos_profile=10)
                    )
                )
            )

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
