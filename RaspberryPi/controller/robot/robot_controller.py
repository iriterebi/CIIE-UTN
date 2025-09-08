"""
TODO
"""

import time
from typing import List
import logging
import serial

class RobotController:
    arduino_port: str
    ser: serial.Serial | None

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.ser = None
        self.logger = logging.getLogger(__name__)

    def connect(self):
        try:
            self.ser = serial.Serial(self.arduino_port, 9600, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            self.logger.info("Connected to Arduino on port %s", self.arduino_port)
        except serial.SerialException as e:
            raise EnvironmentError(f"Error connecting to Arduino: {e}") from e

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.logger.info("Disconnected from Arduino")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()


    def send_command(self, command: str):
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")

        self.logger.debug("Sending command: %s", command)
        try:
            self.ser.write((command + '\n').encode('utf-8'))
            time.sleep(0.1)  # Short delay after sending command
            self.logger.info("Sent command: %s", command)
        except serial.SerialException as e:
            raise EnvironmentError(f"Error sending command to Arduino: {e}") from e

    def read_response(self) -> str:
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")
        try:
            response = self.ser.readline().decode('utf-8').strip()
            self.logger.info("Received response: %s", response)
            return response
        except serial.SerialException as e:
            raise EnvironmentError(f"Error reading response from Arduino: {e}") from e

    def execute_sequence(self, commands: List[str]):
        self.logger.info("Executing command sequence...")
        for command in commands:
            if command:
                self.send_command(command)
                # Optionally read response after each command if needed
                response = self.read_response()
                # print(f"Response for '{command}': {response}")
                print(f"Response for '{command}': {response}")
