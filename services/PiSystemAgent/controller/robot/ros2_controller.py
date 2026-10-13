"""Controlador ROS 2 del robot (IPC interno de la Pi vía DDS).

Expone la misma interfaz duck-typed que `RobotMockController`, pero publica/suscribe
topics ROS 2:

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
import queue
from typing import Any

import rclpy  # import diferido: requiere entorno ROS 2 sourceado
from rclpy.executors import Executor
from rclpy.node import Node
from rclpy.publisher import Publisher
from std_msgs.msg import String

from ..domain import AtomicVar
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

    # deprecated
    robot_commands: RobotCommandRecord

    def __init__(
        self,
        *,
        node_name: str,
        command_topic: str,
        data_topic: str,
        rclExecutor: Executor
    ):
        self.node_name: str = node_name
        self.command_topic: str = command_topic
        self.data_topic: str = data_topic
        self.rclExecutor: Executor = rclExecutor

        self._node: Node | None = None
        self._publisher: Publisher[String] | None = None

        self._latest_status: AtomicVar[dict[str, str]] = AtomicVar({})

        self._connected: bool = False

        self.logger: logging.Logger = logging.getLogger(__name__)
        self.robot_commands = RobotCommandRecord([])

        self._robot_responses: queue.Queue[RobotResponse | None] = queue.Queue()

    def connect(self):
        # Resetear la cola es necesario para sobrevivir un segundo connect() tras un
        # disconnect(): disconnect() llama a stop_reading(), así que si ya había
        # habido uno antes (el ciclo normal: strategy.stop() lo llama explícito y
        # LUEGO disconnect()), ese segundo None queda huérfano. Sin este reset, el
        # próximo read_response() del ciclo nuevo devolvería ese None huérfano en vez
        # de la telemetría real (Finding 1 — ver fix report de Task 4).
        self._robot_responses = queue.Queue()

        self._node = Node(self.node_name)
        self._publisher = self._node.create_publisher(String, self.command_topic, 10)
        _ = self._node.create_subscription(String, self.data_topic, self._on_data, 10)

        _ = self.rclExecutor.add_node(self._node)

        self._connected = True

        self.logger.info(
            "Ros2Controller conectado (node=%s, domain=%s, command_topic=%s, data_topic=%s)",
            self.node_name,
            self._node.context.get_domain_id(),
            self.command_topic,
            self.data_topic,
        )

    def _on_data(self, msg: String):
        """Callback de telemetría (corre en el thread de spin). Solo actualiza snapshot.

        Nunca debe propagar: una excepción aquí sale por `rclpy.spin`, que `_spin`
        trata como fin normal, y el spin se detendría para siempre mientras
        `_connected` sigue en True (telemetría muerta con el agente aparentando salud).
        """
        try:
            self.logger.debug("Telemetría recibida: %s", msg)

            if msg.data.startswith("commands="):
                self.robot_commands = parse_commands(msg.data)
                self._robot_responses.put(CommandsDescriptionRobotResponse(self.robot_commands))
            else:
                parsed = parse_key_value(msg.data)
                if parsed:
                    self._latest_status.mutate(lambda status : (status | parsed))
        except Exception:
            self.logger.exception("Error procesando telemetría: %r", msg.data)

    def disconnect(self):
        self.stop_reading()

        if self._node is not None:
            try:
                _ = self.rclExecutor.remove_node(self._node)
                self._node.destroy_node()
            except Exception:
                self.logger.exception("destroy_node falló")

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

        msg = String()
        msg.data = command
        self._publisher.publish(msg)
        self.logger.info("Comando publicado en %s: %s", self.command_topic, command)

    def read_response(self) -> RobotResponse | None:
        """Bloquea hasta que el robot emita algo. None = señal de parada."""
        return self._robot_responses.get()

    def stop_reading(self) -> None:
        """Desbloquea un read_response() en curso. Idempotente."""
        self._robot_responses.put(None)

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Publicando secuencia de comandos...")
        for command in commands:
            if command:
                self.send_command(command)

    def get_status(self) -> dict[str, Any]:
        """Retorna el último estado de telemetría recibido por DDS."""
        connected = bool(
            self._connected and rclpy.ok()
        )

        telemetry = dict(self._latest_status.get())

        return {
            "status": "online" if connected else "disconnected",
            "mock": False,
            "node": self.node_name,
            "telemetry": telemetry,
        }
