"""Strategy local: robot mock (sin hardware)."""

import logging
from typing import override

from ...robot.robot_mock_controller import RobotMockController
from ..base import OutboxLocalStrategy, State

logger = logging.getLogger(__name__)


class MockStrategy(OutboxLocalStrategy):
    """Wrappea RobotMockController. Mismo comportamiento que SerialStrategy pero sin
    hardware: connect/disconnect son sync, así que no van a executor."""

    def __init__(self, arduino_port: str):
        super().__init__()
        self._robot: RobotMockController = RobotMockController(arduino_port)

    @override
    async def start(self) -> None:
        self._robot.connect()
        self._start_loops()
        self._state = State.RUNNING
        logger.info("MockStrategy iniciado")

    @override
    async def stop(self) -> None:
        # stop_reading ANTES de cancelar: to_thread no se puede cancelar mientras el
        # hilo está bloqueado en read_response.
        self._robot.stop_reading()
        await self._stop_loops()
        self._robot.disconnect()
        self._state = State.STOPPED
        logger.info("MockStrategy detenido")

    @override
    async def pause(self) -> None:
        self.set_telemetry(False)
        await super().pause()
        logger.info("MockStrategy pausado")

    @override
    async def resume(self) -> None:
        self.set_telemetry(True)
        await super().resume()
        logger.info("MockStrategy reanudado")
