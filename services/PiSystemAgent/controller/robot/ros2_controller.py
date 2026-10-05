"""Controlador ROS 2 del robot (IPC interno de la Pi vía DDS).

Expone la misma interfaz duck-typed que `RobotController` (serial) para poder
reutilizar `handle_json_rpc`, pero en vez de hablar serial publica/suscribe topics
ROS 2:

- publica los comandos como `std_msgs/String` en `command_topic`
  (default `inorbit/custom_command`),
- se suscribe a `data_topic` (default `inorbit/custom_data`) para recibir telemetría
  en formato `Key=Value`.

El agente ROS contraparte es *fire-and-forget*: no devuelve una respuesta por comando,
así que `read_response()` retorna un ack sintético solo para mantener la interfaz que
espera `handle_json_rpc`.

`rclpy` se importa de forma **diferida** dentro de `connect()` para que el módulo se
pueda importar (y el modo demo/tests corran) sin tener ROS 2 instalado.
"""

import logging
import os
import re
import threading
from collections.abc import Generator
from typing import Any, Final, override

logger = logging.getLogger(__name__)

# Ack sintético: el agente ROS no responde comandos, devolvemos esto para mantener
# consistencia con la interfaz request/response que espera handle_json_rpc.
_SENT_ACK = "mensaje enviado"


class RobotCommand:
    def valid(self, command: Any) -> bool:  # pyright: ignore[reportAny, reportUnusedParameter]
        ...

    def toDict(self) -> dict[str, Any]: ...


class LiteralRobotCommand(RobotCommand):
    def __init__(self, command: Any) -> None:
        super().__init__()

        self.command: str = command

    @override
    def valid(self, command: Any) -> bool:
        return command == self.command  # pyright: ignore[reportAny]

    @override
    def toDict(self) -> dict[str, Any]:
        return {"_type": "literal", "command": self.command}


class ToggleRobotCommand(RobotCommand):
    def __init__(
        self, command_name: str, command_true: str, command_false: str
    ) -> None:
        super().__init__()
        self.command_true: LiteralRobotCommand = LiteralRobotCommand(command_true)
        self.command_false: LiteralRobotCommand = LiteralRobotCommand(command_false)
        self.command_name: str = command_name

    @override
    def valid(self, command: Any) -> bool:
        return self.command_true.valid(command) or self.command_false.valid(command)

    @override
    def toDict(self) -> dict[str, Any]:
        return {
            "_type": "toggle",
            "mets_name": self.command_name,
            "true": self.command_true.toDict(),
            "false": self.command_false.toDict(),
        }


class TypedRobotCommand(RobotCommand):
    def __init__(self, command_name: str, type_descriptor: str) -> None:
        super().__init__()

        self.type_descriptor: str = type_descriptor
        self.command_name: str = command_name

    @override
    def valid(self, command: Any) -> bool:
        match self.type_descriptor:
            case "uint":
                # bool es subclase de int: no lo aceptamos como entero.
                if isinstance(command, bool):
                    return False
                if isinstance(command, int):
                    return command >= 0
                if isinstance(command, str):
                    try:
                        return int(command) >= 0
                    except ValueError:
                        return False
                return False
            case _:
                return False

    @override
    def toDict(self) -> dict[str, Any]:
        return {
            "_type": "typed-literal",
            "command": self.command_name,
            "type": self.type_descriptor,
        }


class RobotCommandRecord:
    commands: Final[list[RobotCommand]]

    def __init__(self, commands: list[RobotCommand]) -> None:
        self.commands = commands

    def valid(self, command: Any) -> bool:
        # Sin descriptores todavía (el agente ROS aún no publicó `commands=`) no hay
        # contra qué validar: se deja pasar en vez de rechazar todo al arrancar.
        if not self.commands:
            return True

        for c in self.commands:
            if c.valid(command):
                return True

        return False

    def toList(self) -> list[dict[str, Any]]:
        return [c.toDict() for c in self.commands]



def parse_commands(serialiced: str) -> RobotCommandRecord:
    commands_literals = serialiced[len("commands=") :].split(",")
    command_regexp = r"^(<(?P<descriptor>[a-z_:|]+)>)?(?P<meta_command>[a-z_]+)$"
    descriptor_regexp = r"(?P<classifier>[a-z]+)\:(?P<arg>[-a-z_|]+)"

    commands: list[RobotCommand] = []

    for command in commands_literals:
        m = re.search(command_regexp, command)
        if m is None:
            continue

        meta_command = m.group("meta_command")
        descriptor = m.group("descriptor")
        if descriptor is None:
            commands.append(LiteralRobotCommand(meta_command))
            continue

        m2 = re.search(descriptor_regexp, descriptor)
        if m2 is None:
            # invalid command
            continue

        clasifier = m2.group("classifier")
        args = m2.group("arg")

        match clasifier:
            case "toggle":
                s = args.split("|")
                # `toggle` exige exactamente dos literales no vacíos (`<toggle:a|b>`);
                # cualquier otra forma es un descriptor inválido y se descarta.
                if len(s) != 2 or not all(s):
                    logger.warning("Descriptor toggle inválido: %s", command)
                    continue
                commands.append(ToggleRobotCommand(meta_command, s[0], s[1]))
            case "type":
                commands.append(TypedRobotCommand(meta_command, args))
            case _:
                pass

    return RobotCommandRecord(commands)


class RobotResponse:
    command: Final[str | None]

    def __init__(self, command: str | None) -> None:
        self.command = command

    def each(self):
        yield self

    @override
    def __str__(self) -> str: ...


class StrRobotResponse(RobotResponse):
    def __init__(self, command: str | None, string: str) -> None:
        super().__init__(command)

        self.string: str = string

    @override
    def __str__(self) -> str:
        return self.string


class CommandsDescriptionRobotResponse(RobotResponse):
    commands: Final[RobotCommandRecord]

    def __init__(self, commands: RobotCommandRecord) -> None:
        super().__init__(None)

        self.commands = commands

    def toList(self) -> list[dict[str, Any]]:
        return self.commands.toList()


class CommandErrorRobotResponse(RobotResponse):
    def __init__(self, command: str | None, error: Exception) -> None:
        super().__init__(command)

        self.error: Exception = error

    @override
    def __str__(self) -> str:
        return str(self.error)


class ComposedRobotResponse(RobotResponse):
    commands: Final[list[RobotResponse]]

    def __init__(self, commands: list[RobotResponse]) -> None:
        super().__init__(None)

        self.commands = commands

    @override
    def each(self) -> Generator[RobotResponse, Any]:
        yield from self.commands


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

        self.robot_response: list[RobotResponse] = []
        self._robot_response_lock: threading.Lock = threading.Lock()

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

            with self._robot_response_lock:
                self.robot_response.append(
                    CommandsDescriptionRobotResponse(self.robot_commands)
                )
        else:
            parsed = parse_key_value(msg.data)
            if parsed:
                with self._status_lock:
                    self._latest_status.update(parsed)
            self.logger.debug("Telemetría recibida: %s", msg.data)

    def disconnect(self):
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
        msg = self._string_cls()

        if not self.robot_commands.valid(command):
            with self._robot_response_lock:
                self.robot_response.append(
                    CommandErrorRobotResponse(
                        command, RuntimeWarning("invalid command")
                    )
                )

            self.logger.warning("Comando inválido: %s", command)
            return

        msg.data = command
        self._publisher.publish(msg)
        self.logger.info("Comando publicado en %s: %s", self.command_topic, command)
        with self._robot_response_lock:
            self.robot_response.append(StrRobotResponse(command, _SENT_ACK))

    def read_response(self) -> RobotResponse:
        """El agente ROS no responde comandos: devolvemos un ack sintético."""
        with self._robot_response_lock:
            responses = self.robot_response
            self.robot_response = []

        if len(responses) == 1:
            return responses[0]

        return ComposedRobotResponse(responses)

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
