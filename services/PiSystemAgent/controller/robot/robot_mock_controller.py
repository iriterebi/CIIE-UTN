import logging
import random
import threading
from typing import Any

from .ros2_controller import (
    CommandsDescriptionRobotResponse,
    ComposedRobotResponse,
    LiteralRobotCommand,
    RobotCommandRecord,
    RobotResponse,
    StrRobotResponse,
    ToggleRobotCommand,
)


class RobotMockController:
    arduino_port: str

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.logger = logging.getLogger(__name__)
        self.logger.warning("RobotMockController is active. No physical robot commands will be sent.")

        self.robot_response: list[RobotResponse] = [
            CommandsDescriptionRobotResponse(RobotCommandRecord([
                ToggleRobotCommand("play", "start", "stop"),
                LiteralRobotCommand("restart")
            ]))
        ]

        self._robot_response_lock: threading.Lock = threading.Lock()


    def connect(self):
        self.logger.info("Mock robot connected (no-op).")

    def disconnect(self):
        self.logger.info("Mock robot disconnected (no-op).")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def send_command(self, command: str):
        self.logger.info(f"Mock robot received command: {command}")
        with self._robot_response_lock:
            self.robot_response.append(StrRobotResponse(command, "OK"))

    def read_response(self) -> RobotResponse:
        self.logger.info("Mock robot returning dummy response.")

        with self._robot_response_lock:
            responses = self.robot_response
            self.robot_response = []

        if len(responses) == 1:
            return responses[0]

        return ComposedRobotResponse(responses)

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Mock robot executing command sequence (simulated):")
        for command in commands:
            if command:
                self.send_command(command)
                response = self.read_response()
                self.logger.info("Mock Response for '%s': %s", command, response)

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
