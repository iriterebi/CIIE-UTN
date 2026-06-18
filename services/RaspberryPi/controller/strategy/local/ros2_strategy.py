"""Strategy local: comunicación con el robot vía ROS 2 (IPC interno de la Pi)."""

import asyncio
import logging
from typing import Any, override

from ..base import LocalStrategy, State
from ...robot.ros2_controller import Ros2Controller
from ...json_rpc import (
    JsonRpcCommand, JsonRpcResponse, handle_json_rpc, create_status_notification,
)

logger = logging.getLogger(__name__)

_STATUS_INTERVAL_SEC = 5.0


class Ros2Strategy(LocalStrategy):
    """Wrappea Ros2Controller para implementar la interfaz Strategy.

    Traduce comandos JSON-RPC (formato interno) a publicaciones ROS 2
    y produce respuestas (ack) + status periódico desde la telemetría DDS.
    """

    def __init__(self, *, node_name: str, command_topic: str, data_topic: str, domain_id: int = 42):
        self._robot = Ros2Controller(
            node_name=node_name,
            command_topic=command_topic,
            data_topic=data_topic,
            domain_id=domain_id,
        )
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._telemetry_enabled: bool = True
        self._telemetry_task: asyncio.Task[None] | None = None

    @override
    def get_telemetry_enabled(self):
        return self._telemetry_enabled

    @override
    def set_telemetry(self, enabled: bool) -> None:
        self._telemetry_enabled = enabled
        if enabled and (self._telemetry_task is None or self._telemetry_task.done()):
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        elif not enabled and self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
            self._telemetry_task = None
        logger.info("Telemetría ROS 2 %s", "habilitada" if enabled else "deshabilitada")

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        self._state = State.RUNNING
        logger.info("Ros2Strategy iniciado (node: %s)", self._robot.node_name)

    @override
    async def stop(self) -> None:
        if self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
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

    @override
    async def receive(self) -> Any:
        """Pull del outbox — telemetría y respuestas llegan por la misma cola."""
        return await self._outbox.get()

    async def _telemetry_loop(self) -> None:
        """Encola status periódico mientras esté habilitada."""
        try:
            while True:
                await asyncio.sleep(_STATUS_INTERVAL_SEC)
                notification = create_status_notification(self._robot.get_status())
                await self._outbox.put(notification.model_dump(mode="json"))
        except asyncio.CancelledError:
            pass

    @override
    async def send(self, message: Any) -> None:
        """Recibe un comando en formato interno, lo publica vía ROS 2."""
        command = JsonRpcCommand.model_validate(message)
        response: JsonRpcResponse = await handle_json_rpc(command, self._robot)
        await self._outbox.put(response.model_dump(mode="json"))
