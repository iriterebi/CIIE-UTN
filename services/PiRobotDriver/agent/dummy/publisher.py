"""
Dummy publisher node. Publishes fake fluctuating sensor data to /inorbit/custom_data.
Use this to test the InOrbit data pipeline without any hardware connected.
"""
import random

from rclpy.node import Node
from rclpy.publisher import Publisher as RclPublisher
from std_msgs.msg import String

from ..domain.publisher_info import TopicInfo


class Publisher(Node):
    def __init__(self, topic_info: TopicInfo):
        super().__init__('agente_serial_node')
        self.publisher_: RclPublisher[String] = self.create_publisher(String, topic_info.topic, topic_info.qos_profile)
        self.timer = self.create_timer(1.0, self.timer_callback)
        _ = self.get_logger().info('Nodo Publicador Dummy Iniciado')

    def timer_callback(self):
        # dummy simulado de dato fluctuante
        msg = String()
        msg.data = f"data_dummy={round(random.uniform(20.0, 30.0), 2)}"
        self.publisher_.publish(msg)
        _ = self.get_logger().info(f'Publicando: {msg.data}')
