"""Strategy local: comunicación serial con Arduino."""

import asyncio
from typing import override

from ...robot.robot_controller import RobotController
from ..base import OutboxLocalStrategy


class SerialStrategy(OutboxLocalStrategy):
    """Wrappea RobotController. El ciclo de vida (orden de start/stop, pause/resume)
    lo aporta OutboxLocalStrategy; acá sólo vive cómo conectar/desconectar el puerto."""

    def __init__(self, arduino_port: str):
        super().__init__()
        self._robot: RobotController = RobotController(arduino_port)

    @override
    async def _connect_robot(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)

    @override
    async def _disconnect_robot(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.disconnect)

    @override
    def _start_log_detail(self) -> str:
        return f"puerto: {self._robot.arduino_port}"
