"""Strategy local: comunicación con el robot vía ROS 2 (IPC interno de la Pi)."""

import asyncio
import logging
from typing import override

from ...robot.ros2_controller import Ros2Controller
from ..base import OutboxLocalStrategy, State

logger = logging.getLogger(__name__)


class Ros2Strategy(OutboxLocalStrategy):
    """Wrappea Ros2Controller. La cola, los loops y la traducción a JSON-RPC los
    aporta OutboxLocalStrategy; acá sólo vive el ciclo de vida del nodo."""

    def __init__(
        self,
        *,
        node_name: str,
        command_topic: str,
        data_topic: str,
        domain_id: int = 42,
    ):
        super().__init__()
        self._robot: Ros2Controller = Ros2Controller(
            node_name=node_name,
            command_topic=command_topic,
            data_topic=data_topic,
            domain_id=domain_id,
        )

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)
        self._start_loops()
        self._state = State.RUNNING
        logger.info("Ros2Strategy iniciado (node: %s)", self._robot.node_name)

    @override
    async def stop(self) -> None:
        # stop_reading ANTES de cancelar: to_thread no se puede cancelar mientras el
        # hilo está bloqueado en read_response.
        self._robot.stop_reading()
        await self._stop_loops()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.disconnect)
        self._state = State.STOPPED
        logger.info("Ros2Strategy detenido")

    @override
    async def pause(self) -> None:
        self.set_telemetry(False)
        await super().pause()
        logger.info("Ros2Strategy pausado")

    @override
    async def resume(self) -> None:
        self.set_telemetry(True)
        await super().resume()
        logger.info("Ros2Strategy reanudado")
