import logging
import random
from typing import List

class RobotMockController:
    arduino_port: str

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.logger = logging.getLogger(__name__)
        self.logger.warning("RobotMockController is active. No physical robot commands will be sent.")

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

    def read_response(self) -> str:
        self.logger.info("Mock robot returning dummy response.")
        return "OK"

    def execute_sequence(self, commands: List[str]):
        self.logger.info("Mock robot executing command sequence (simulated):")
        for command in commands:
            if command:
                self.send_command(command)
                response = self.read_response()
                self.logger.info("Mock Response for '%s': %s", command, response)

    def get_status(self) -> dict:
        """Retorna estado simulado del robot mock."""
        return {
            "status": "online",
            "mock": True,
            "servos": {
                "base": random.randint(0, 180),
                "cuerpo": random.randint(0, 180),
                "hombro": random.randint(0, 180),
                "brazo": random.randint(0, 180),
                "antebrazo_1": random.randint(0, 180),
                "antebrazo_2": random.randint(0, 180),
                "mano": random.randint(0, 180),
            },
        }
