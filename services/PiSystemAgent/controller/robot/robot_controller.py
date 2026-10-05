"""
TODO
"""

import logging
import threading
import time
from typing import Any

import serial

from .responses import RobotResponse, StrRobotResponse


class RobotController:
    arduino_port: str
    ser: serial.Serial | None

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.ser = None
        self.logger = logging.getLogger(__name__)
        self._stop = threading.Event()

    def connect(self):
        # Resetear el Event es necesario para sobrevivir un segundo connect() tras un
        # disconnect(): sin esto, un stop_reading() previo lo deja en True para
        # siempre y read_response() devuelve None de inmediato en todo el ciclo
        # siguiente (Finding 1 — ver fix report de Task 4).
        self._stop.clear()
        try:
            self.ser = serial.Serial(self.arduino_port, 9600, timeout=1)
            time.sleep(2)  # Wait for Arduino to initialize
            self.logger.info("Connected to Arduino on port %s", self.arduino_port)
        except serial.SerialException as e:
            raise EnvironmentError(f"Error connecting to Arduino: {e}") from e

    def disconnect(self):
        self.stop_reading()
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
            _ = self.ser.write((command + "\n").encode("utf-8"))
            time.sleep(0.1)  # Short delay after sending command
            self.logger.info("Sent command: %s", command)
        except serial.SerialException as e:
            raise EnvironmentError(f"Error sending command to Arduino: {e}") from e

    def read_response(self) -> RobotResponse | None:
        """Bloquea hasta que el Arduino emita una línea. None = señal de parada.

        El puerto tiene timeout=1, así que readline() devuelve b'' cada segundo sin
        datos. Esos vacíos se descartan: son el punto donde se chequea la parada.

        El chequeo de `_stop` va ANTES del de conexión: una llamada perdida tras
        `disconnect()` (stop_reading() ya corrido, puerto ya cerrado) debe devolver
        el sentinel como cualquier otra, no levantar `ConnectionError` — mismo
        contrato que `RobotMockController`/`Ros2Controller` (su `queue.get()` no
        distingue, siempre respeta el sentinel ya encolado).
        """
        if self._stop.is_set():
            return None
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")

        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode("utf-8").strip()
            except serial.SerialException as e:
                raise EnvironmentError(
                    f"Error reading response from Arduino: {e}"
                ) from e
            if line:
                self.logger.info("Received response: %s", line)
                return StrRobotResponse(line)

        return None

    def stop_reading(self) -> None:
        """Desbloquea un read_response() en curso (a más tardar en un timeout)."""
        self._stop.set()

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Executing command sequence...")
        for command in commands:
            if command:
                self.send_command(command)

    def get_status(self) -> dict[str, Any]:
        """Retorna el estado actual del robot."""
        return {
            "status": "online" if self.ser and self.ser.is_open else "disconnected",
            "mock": False,
            "port": self.arduino_port,
        }
