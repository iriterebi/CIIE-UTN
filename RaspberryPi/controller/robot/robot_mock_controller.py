import logging
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
                print(f"Mock Response for '{command}': {response}")
