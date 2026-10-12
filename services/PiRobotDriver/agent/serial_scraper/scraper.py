"""
Serial scraper node. Reads data from Arduino via serial and publishes to /inorbit/custom_data.
Also subscribes to /inorbit/custom_command and writes received commands back to serial.
"""

import re
from typing import override

import serial
from rclpy.node import Node
from rclpy.publisher import Publisher
from rclpy.subscription import Subscription
from rclpy.timer import Timer
from std_msgs.msg import String

from ..domain.publisher_info import TopicInfo

MODO_MAP = {
    "sweep_start": "barridoEnCurso",
    "sweep_end": "barridoCompletado",
    "sweep_aborted": "barridoAbortado",
    "experiment_restart": "reinicio",
    "motor_stopped": "motorDetenido",
    "MRUV motor controller ready": "listo",
}


class SerialScraper(Node):
    def __init__(self, *, serial_port: str, baud_rate: int, publisher_info: TopicInfo, subscription_info: TopicInfo):
        super().__init__("serial_scraper_node")
        self.publisher_: Publisher[String] = self.create_publisher(String, publisher_info.topic, publisher_info.qos_profile)
        self.subscription: Subscription[String] = self.create_subscription(
            String, subscription_info.topic, self.command_callback, subscription_info.qos_profile
        )
        self.ser: serial.Serial = serial.Serial(serial_port, baud_rate, timeout=1)
        _ = self.get_logger().info(
            f"Serial scraper started on {serial_port} at {baud_rate} baud"
        )
        self.timer: Timer = self.create_timer(0.1, self.read_serial)
        self._modo: str = "listo"
        self._pwm: int = 0
        self._tension: int = 0

    def command_callback(self, msg: String):
        line = msg.data.strip() + "\n"
        _ = self.ser.write(line.encode("utf-8"))
        _ = self.get_logger().info(f"Sent to serial: {msg.data}")

    def read_serial(self):
        if self.ser.in_waiting > 0:
            raw = self.ser.readline().decode("utf-8", errors="ignore").strip()
            if not raw:
                return

            pwm_match = re.search(r"pwm=(\d+)", raw)
            tension_match = re.search(r"tension en gramos=(\d+)", raw)

            if raw in MODO_MAP:
                self._modo = MODO_MAP[raw]
            elif raw.startswith("t="):
                self._modo = "enOperacion"
            elif pwm_match and not raw.startswith("t="):
                self._modo = "barridoEnCurso"
            if pwm_match:
                self._pwm = int(pwm_match.group(1))
            if tension_match:
                self._tension = int(tension_match.group(1))

            for kv in [
                f"Modo={self._modo}",
                f"Tension={self._tension}",
                f"Velocidad={self._pwm}",
            ]:
                m = String()
                m.data = kv
                self.publisher_.publish(m)

            _ = self.get_logger().info(
                f"Modo={self._modo} Tension={self._tension} Velocidad={self._pwm}"
            )

    @override
    def destroy_node(self):
        self.ser.close()
        super().destroy_node()
