"""Strategy local: comunicación con el robot vía ROS 2 (IPC interno de la Pi)."""

import asyncio
from typing import override

from rclpy.executors import Executor

from ...robot.ros2_controller import Ros2Controller
from ..base import OutboxLocalStrategy


class Ros2Strategy(OutboxLocalStrategy):
    """Wrappea Ros2Controller. El ciclo de vida (orden de start/stop, pause/resume)
    lo aporta OutboxLocalStrategy; acá sólo vive cómo conectar/desconectar el nodo."""

    def __init__(
        self,
        *,
        node_name: str,
        command_topic: str,
        data_topic: str,
        rclExecutor: Executor
    ):
        super().__init__()
        self._robot: Ros2Controller = Ros2Controller(
            node_name=node_name,
            command_topic=command_topic,
            data_topic=data_topic,
            rclExecutor=rclExecutor
        )

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
        return f"node: {self._robot.node_name}"
