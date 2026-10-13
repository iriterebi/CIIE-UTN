import logging
import queue
import random
from typing import Any

from .responses import (
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
    LiteralRobotCommand,
    RobotCommandRecord,
    RobotResponse,
    StrRobotResponse,
    ToggleRobotCommand,
)


class RobotMockController:
    """Robot simulado. Replica el contrato real, validación de comandos incluida,
    para que el modo demo ejercite de verdad el autodescubrimiento."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.warning(
            "RobotMockController is active. No physical robot commands will be sent."
        )

        self.robot_commands: RobotCommandRecord = RobotCommandRecord([
            ToggleRobotCommand("play", "start", "stop"),
            LiteralRobotCommand("restart"),
        ])
        self._responses: queue.Queue[RobotResponse | None] = queue.Queue()

    def connect(self):
        # Resetear la cola es necesario para sobrevivir un segundo connect() tras un
        # disconnect(): disconnect() llama a stop_reading(), así que si ya había
        # habido uno antes (el ciclo normal: strategy.stop() lo llama explícito y
        # LUEGO disconnect()), ese segundo None queda huérfano. Sin este reset, el
        # próximo connect() encolaría los descriptores detrás del huérfano y el
        # primer read_response() del ciclo nuevo devolvería None en vez de los
        # descriptores (Finding 1 — ver fix report de Task 4).
        self._responses = queue.Queue()
        # Publicar los descriptores al conectar imita al agente real, que los manda
        # por telemetría apenas arranca.
        self._responses.put(CommandsDescriptionRobotResponse(self.robot_commands))
        self.logger.info("Mock robot connected (no-op).")

    def disconnect(self):
        self.stop_reading()
        self.logger.info("Mock robot disconnected (no-op).")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def send_command(self, command: str):
        if not self.robot_commands.valid(command):
            self.logger.warning("Comando inválido: %s", command)
            raise InvalidCommandError(f"comando desconocido: {command}")

        self.logger.info("Mock robot received command: %s", command)
        self._responses.put(StrRobotResponse("OK"))

    def read_response(self) -> RobotResponse | None:
        return self._responses.get()

    def stop_reading(self) -> None:
        self._responses.put(None)

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Mock robot executing command sequence (simulated):")
        for command in commands:
            if command:
                self.send_command(command)

    def get_status(self) -> dict[str, Any]:
        """Retorna estado simulado del robot mock."""
        return {
            "status": "online",
            "mock": True,
            "sensors": {
                "base": random.randint(0, 180),
                "cuerpo": random.randint(0, 180),
                "hombro": random.randint(0, 180),
                "brazo": random.randint(0, 180),
                "antebrazo_1": random.randint(0, 180),
                "antebrazo_2": random.randint(0, 180),
                "mano": random.randint(0, 180),
            },
        }
