"""Strategy local: robot mock (sin hardware)."""

from typing import override

from ...robot.robot_mock_controller import RobotMockController
from ..base import OutboxLocalStrategy


class MockStrategy(OutboxLocalStrategy):
    """Wrappea RobotMockController. El ciclo de vida (orden de start/stop,
    pause/resume) lo aporta OutboxLocalStrategy; a diferencia de ROS 2,
    connect/disconnect son sync acá, así que no van a executor."""

    def __init__(self):
        super().__init__()
        self._robot: RobotMockController = RobotMockController()

    @override
    async def _connect_robot(self) -> None:
        self._robot.connect()

    @override
    async def _disconnect_robot(self) -> None:
        self._robot.disconnect()
