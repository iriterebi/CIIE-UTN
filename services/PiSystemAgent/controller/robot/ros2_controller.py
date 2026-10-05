"""Controlador ROS 2 del robot (IPC interno de la Pi vía DDS).

Expone la misma interfaz duck-typed que `RobotController` (serial) y
`RobotMockController`, pero en vez de hablar serial publica/suscribe topics ROS 2:

- publica los comandos como `std_msgs/String` en `command_topic`
  (default `inorbit/custom_command`),
- se suscribe a `data_topic` (default `inorbit/custom_data`) para recibir telemetría
  en formato `Key=Value`.

El agente ROS contraparte es *fire-and-forget*: no devuelve una respuesta por comando.
`send_command()` sólo valida y publica (levanta si el comando es inválido o si no hay
conexión); `read_response()` bloquea hasta que llegue algo por `data_topic` (una
telemetría o, cuando el payload empieza con `commands=`, el redescubrimiento de
comandos) y `None` es la señal de parada.

`rclpy` se importa de forma **diferida** dentro de `connect()` para que el módulo se
pueda importar (y el modo demo/tests corran) sin tener ROS 2 instalado.
"""

import logging
import os
import threading
import queue
from typing import Any

from .responses import (
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
    RobotCommandRecord,
    RobotResponse,
    parse_commands,
)

logger = logging.getLogger(__name__)


def parse_key_value(data: str) -> dict[str, str]:
    """Parsea un string de telemetría `Key=Value` en un dict.

    Lenient: acepta uno o varios pares separados por espacios, comas o punto y coma.
    Ej: `"base=90, mano=10"` → `{"base": "90", "mano": "10"}`.
    Los fragmentos sin `=` se ignoran.
    """

    result: dict[str, str] = {}
    for token in data.replace(",", " ").replace(";", " ").split():
        if "=" in token:
            key, _, value = token.partition("=")
            key = key.strip()
            if key:
                result[key] = value.strip()
    return result


class Ros2Controller:
    """Wrappea un nodo rclpy con la interfaz duck-typed del controlador del robot."""

    robot_commands: RobotCommandRecord

    def __init__(
        self,
        *,
        node_name: str,
        command_topic: str,
        data_topic: str,
        domain_id: int = 42,
    ):
        self.node_name: str = node_name
        self.command_topic: str = command_topic
        self.data_topic: str = data_topic
        self.domain_id: int = domain_id

        self._rclpy: Any = None
        self._string_cls: Any = None
        self._node: Any = None
        self._publisher: Any = None
        self._spin_thread: threading.Thread | None = None

        self._latest_status: dict[str, str] = {}
        self._status_lock: threading.Lock = threading.Lock()
        self._connected: bool = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.robot_commands = RobotCommandRecord([])

        self._responses: queue.Queue[RobotResponse | None] = queue.Queue()

    def connect(self):
        # Fija el dominio DDS (debe coincidir con el agente ROS) vía la env var estándar que rclpy
        # lee en rclpy.init(). setdefault respeta un ROS_DOMAIN_ID externo si ya está seteado.
        os.environ.setdefault("ROS_DOMAIN_ID", str(self.domain_id))
        try:
            import rclpy  # import diferido: requiere entorno ROS 2 sourceado
            from rclpy.node import Node
            from std_msgs.msg import String
        except ImportError as e:
            raise OSError(
                "No se pudo importar rclpy/std_msgs. Asegúrate de sourcear el entorno "
                + "ROS 2 en la Pi (ej. `source /opt/ros/<distro>/setup.bash`) antes de "
                + "usar Ros2Strategy."
            ) from e

        self._rclpy = rclpy
        self._string_cls = String

        if not rclpy.ok():
            rclpy.init()

        self._node = Node(self.node_name)
        self._publisher = self._node.create_publisher(String, self.command_topic, 10)
        self._node.create_subscription(String, self.data_topic, self._on_data, 10)

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()
        self._connected = True
        self.logger.info(
            "Ros2Controller conectado (node=%s, domain=%s, command_topic=%s, data_topic=%s)",
            self.node_name,
            os.environ.get("ROS_DOMAIN_ID"),
            self.command_topic,
            self.data_topic,
        )

    def _spin(self):
        """Corre rclpy.spin en un daemon thread (asyncio queda en el main thread)."""
        try:
            self._rclpy.spin(self._node)
        except (
            Exception
        ) as e:  # spin levanta al hacer shutdown; lo tratamos como fin normal
            self.logger.debug("rclpy.spin finalizó: %s", e)

    def _on_data(self, msg):
        """Callback de telemetría (corre en el thread de spin). Solo actualiza snapshot.

        Nunca debe propagar: una excepción aquí sale por `rclpy.spin`, que `_spin`
        trata como fin normal, y el spin se detendría para siempre mientras
        `_connected` sigue en True (telemetría muerta con el agente aparentando salud).
        """
        try:
            self._handle_data(msg)
        except Exception:
            self.logger.exception("Error procesando telemetría: %r", msg.data)

    def _handle_data(self, msg):
        if isinstance(msg.data, str) and msg.data.startswith("commands="):  # pyright: ignore[reportUnknownMemberType]
            self.robot_commands = parse_commands(msg.data)
            self._responses.put(CommandsDescriptionRobotResponse(self.robot_commands))
        else:
            parsed = parse_key_value(msg.data)
            if parsed:
                with self._status_lock:
                    self._latest_status.update(parsed)
            self.logger.debug("Telemetría recibida: %s", msg.data)

    def disconnect(self):
        self.stop_reading()
        if self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()
        if self._spin_thread is not None and self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2)
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception as e:
                self.logger.debug("destroy_node falló: %s", e)
        self._connected = False
        self.logger.info("Ros2Controller desconectado")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def send_command(self, command: str):
        if not self._connected or self._publisher is None:
            raise ConnectionError(
                "Ros2Controller no conectado. Llama a connect() primero."
            )

        if not self.robot_commands.valid(command):
            self.logger.warning("Comando inválido: %s", command)
            raise InvalidCommandError(f"comando desconocido: {command}")

        msg = self._string_cls()
        msg.data = command
        self._publisher.publish(msg)
        self.logger.info("Comando publicado en %s: %s", self.command_topic, command)

    def read_response(self) -> RobotResponse | None:
        """Bloquea hasta que el robot emita algo. None = señal de parada."""
        return self._responses.get()

    def stop_reading(self) -> None:
        """Desbloquea un read_response() en curso. Idempotente."""
        self._responses.put(None)

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Publicando secuencia de comandos...")
        for command in commands:
            if command:
                self.send_command(command)

    def get_status(self) -> dict[str, Any]:
        """Retorna el último estado de telemetría recibido por DDS."""
        connected = bool(
            self._connected and self._rclpy is not None and self._rclpy.ok()
        )
        with self._status_lock:
            telemetry = dict(self._latest_status)
        return {
            "status": "online" if connected else "disconnected",
            "mock": False,
            "node": self.node_name,
            "telemetry": telemetry,
        }
