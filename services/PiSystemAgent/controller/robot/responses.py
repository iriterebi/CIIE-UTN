"""Vocabulario de dominio del robot: descriptores de comandos y respuestas.

Vive aparte de los controladores porque los dos (`ros2_controller`,
`robot_mock_controller`) y el adapter `json_rpc` lo comparten.
Antes estaba dentro de `ros2_controller.py`, lo que acoplaba el mock al
módulo de ROS 2.

Regla de correlación: el TIPO decide el sobre JSON-RPC.
`DispatchOkRobotResponse`/`DispatchErrorRobotResponse` son el resultado de despachar
un comando del usuario y llevan `request_id`; todo lo demás es output espontáneo del
robot y sale como notification.
"""

import logging
import re
from typing import Any, Final, override

logger = logging.getLogger(__name__)

# Payload por defecto del ack de despacho. Ni el Arduino ni el agente ROS 2 confirman
# ejecución, así que lo único afirmable es que el comando salió.
SENT_ACK = "mensaje enviado"


class InvalidCommandError(ValueError):
    """El comando no matchea ningún descriptor publicado por el robot."""


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
    """Algo que sale del robot hacia el usuario.

    `request_id` es el valor que se copia al campo `id` del sobre JSON-RPC, no el
    criterio para elegir el sobre: eso lo decide el tipo concreto (ver `to_jsonrpc`).
    Sólo las subclases de despacho lo setean.
    """

    request_id: Final[str | int | None]

    def __init__(self, request_id: str | int | None = None) -> None:
        self.request_id = request_id

    @override
    def __str__(self) -> str:
        return type(self).__name__


class StrRobotResponse(RobotResponse):
    """Output crudo del robot (una línea del Arduino, un mensaje suelto)."""

    text: Final[str]

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    @override
    def __str__(self) -> str:
        return self.text


class CommandsDescriptionRobotResponse(RobotResponse):
    """Los descriptores de comandos que el robot publicó (autodescubrimiento)."""

    commands: Final[RobotCommandRecord]

    def __init__(self, commands: RobotCommandRecord) -> None:
        super().__init__()
        self.commands = commands

    def toList(self) -> list[dict[str, Any]]:
        return self.commands.toList()


class StatusRobotResponse(RobotResponse):
    """Snapshot de telemetría. Lo produce el loop periódico, no el robot."""

    status: Final[dict[str, Any]]

    def __init__(self, status: dict[str, Any]) -> None:
        super().__init__()
        self.status = status


class DispatchOkRobotResponse(RobotResponse):
    """El comando se validó y salió. NO afirma que el robot lo haya ejecutado."""

    method: Final[str]
    detail: Final[str]
    commands_count: Final[int | None]

    def __init__(
        self,
        request_id: str | int | None,
        method: str,
        detail: str = SENT_ACK,
        commands_count: int | None = None,
    ) -> None:
        super().__init__(request_id)
        self.method = method
        self.detail = detail
        self.commands_count = commands_count

    @override
    def __str__(self) -> str:
        return self.detail


class DispatchErrorRobotResponse(RobotResponse):
    """El comando no se pudo despachar: inválido, o falló el transporte."""

    method: Final[str]
    error: Final[Exception]

    def __init__(
        self, request_id: str | int | None, method: str, error: Exception
    ) -> None:
        super().__init__(request_id)
        self.method = method
        self.error = error

    @override
    def __str__(self) -> str:
        return str(self.error)
