from dataclasses import dataclass

from rclpy.qos import QoSProfile


@dataclass(frozen=True)
class TopicInfo:
    topic: str
    qos_profile: QoSProfile | int
