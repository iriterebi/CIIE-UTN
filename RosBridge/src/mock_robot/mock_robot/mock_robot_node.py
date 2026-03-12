"""
Nodo ROS 2 que simula robots para modo demo.

Lee DEMO_ROBOT_IDS del entorno (UUIDs separados por coma),
se suscribe a los topics de comandos de cada robot y publica
respuestas simuladas y actualizaciones de estado periódicas.
"""

import json
import os
import random
import uuid

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


# --- Crockford Base32 encoding ---

_CROCKFORD_ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def _uuid_to_crockford_base32(uuid_str: str) -> str:
    """Convierte un UUID (string) a Crockford Base32."""
    u = uuid.UUID(uuid_str)
    n = u.int
    if n == 0:
        return '0'
    chars = []
    while n > 0:
        chars.append(_CROCKFORD_ALPHABET[n & 0x1F])
        n >>= 5
    return ''.join(reversed(chars))


# --- Nodo Mock ---

_DEFAULT_DEMO_IDS = 'a0e1f2a3-b4c5-d6e7-f8a9-b0c1d2e3f4a5'
_STATUS_INTERVAL_SEC = 5.0
_RESPONSE_DELAY_MIN = 0.1
_RESPONSE_DELAY_MAX = 0.5


class MockRobotNode(Node):
    """Simula uno o más robots: recibe comandos, responde con datos ficticios."""

    def __init__(self):
        super().__init__('mock_robot_node')

        raw_ids = os.environ.get('DEMO_ROBOT_IDS', _DEFAULT_DEMO_IDS)
        self._robots: list[dict] = []

        for uid in raw_ids.split(','):
            uid = uid.strip()
            if not uid:
                continue
            b32 = _uuid_to_crockford_base32(uid)
            robot = {
                'uuid': uid,
                'base32': b32,
                'publisher_response': self.create_publisher(
                    String, f'/robot/{b32}/response', 10
                ),
                'publisher_status': self.create_publisher(
                    String, f'/robot/{b32}/status', 10
                ),
            }
            self.create_subscription(
                String,
                f'/robot/{b32}/command',
                lambda msg, r=robot: self._on_command(msg, r),
                10,
            )
            self._robots.append(robot)
            self.get_logger().info(
                f'Mock robot registrado: {uid} → /robot/{b32}/*'
            )

        # Timer para publicar status periódico
        self.create_timer(_STATUS_INTERVAL_SEC, self._publish_status)

    def _on_command(self, msg: String, robot: dict):
        """Recibe un comando y publica una respuesta simulada."""
        self.get_logger().info(
            f'[{robot["base32"]}] Comando recibido: {msg.data}'
        )

        try:
            command = json.loads(msg.data)
            method = command.get('method', 'unknown')
        except (json.JSONDecodeError, AttributeError):
            method = 'unknown'

        response = String()
        response.data = json.dumps({
            'jsonrpc': '2.0',
            'result': {
                'status': 'ok',
                'method': method,
                'message': f'Mock ejecutó: {method}',
                'simulated_delay': round(
                    random.uniform(_RESPONSE_DELAY_MIN, _RESPONSE_DELAY_MAX), 3
                ),
            },
            'id': command.get('id') if isinstance(command, dict) else None,
        })
        robot['publisher_response'].publish(response)
        self.get_logger().info(
            f'[{robot["base32"]}] Respuesta enviada para: {method}'
        )

    def _publish_status(self):
        """Publica estado periódico para cada robot mock."""
        for robot in self._robots:
            status = String()
            status.data = json.dumps({
                'robot_id': robot['uuid'],
                'status': 'online',
                'mock': True,
                'servos': {
                    'base': random.randint(0, 180),
                    'cuerpo': random.randint(0, 180),
                    'hombro': random.randint(0, 180),
                    'brazo': random.randint(0, 180),
                    'antebrazo_1': random.randint(0, 180),
                    'antebrazo_2': random.randint(0, 180),
                    'mano': random.randint(0, 180),
                },
            })
            robot['publisher_status'].publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = MockRobotNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
