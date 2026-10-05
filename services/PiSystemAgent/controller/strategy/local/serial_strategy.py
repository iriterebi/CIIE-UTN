"""Strategy local: comunicación serial con Arduino."""

import asyncio
import logging
from typing import override

from ...robot.robot_controller import RobotController
from ..base import OutboxLocalStrategy, State

logger = logging.getLogger(__name__)


class SerialStrategy(OutboxLocalStrategy):
    """Wrappea RobotController. La cola, los loops y la traducción a JSON-RPC los
    aporta OutboxLocalStrategy; acá sólo vive el ciclo de vida del puerto."""

    def __init__(self, arduino_port: str):
        super().__init__()
        self._robot: RobotController = RobotController(arduino_port)

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)
        self._start_loops()
        self._state = State.RUNNING
        logger.info("SerialStrategy iniciado (puerto: %s)", self._robot.arduino_port)

    @override
    async def stop(self) -> None:
        # stop_reading ANTES de cancelar: to_thread no se puede cancelar mientras el
        # hilo está bloqueado en read_response.
        self._robot.stop_reading()
        await self._stop_loops()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.disconnect)
        self._state = State.STOPPED
        logger.info("SerialStrategy detenido")

    @override
    async def pause(self) -> None:
        self.set_telemetry(False)
        await super().pause()
        logger.info("SerialStrategy pausado")

    @override
    async def resume(self) -> None:
        self.set_telemetry(True)
        await super().resume()
        logger.info("SerialStrategy reanudado")
