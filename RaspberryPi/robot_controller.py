# import os
# import requests
import serial
import time
from typing import List
from contextlib import contextmanager

class RobotController:
    arduino_port: str
    ser: serial.Serial | None

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.arduino_port, 9600, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            print(f"Connected to Arduino on port {self.arduino_port}")
        except serial.SerialException as e:
            raise EnvironmentError(f"Error connecting to Arduino: {e}")

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Disconnected from Arduino")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()


    def send_command(self, command: str):
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")

        print(f"Sending command: {command}")
        try:
            self.ser.write((command + '\n').encode('utf-8'))
            time.sleep(0.1)  # Short delay after sending command
            print(f"Sent command: {command}")
        except serial.SerialException as e:
            raise EnvironmentError(f"Error sending command to Arduino: {e}")

    def read_response(self) -> str:
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")
        try:
            response = self.ser.readline().decode('utf-8').strip()
            print(f"Received response: {response}")
            return response
        except serial.SerialException as e:
            raise EnvironmentError(f"Error reading response from Arduino: {e}")

    def execute_sequence(self, commands: List[str]):
        print("Executing commands:")
        for command in commands:
            if command:
                self.send_command(command)
                # Optionally read response after each command if needed
                response = self.read_response()
                # print(f"Response for '{command}': {response}")
                print(f"Response for '{command}': {response}")
