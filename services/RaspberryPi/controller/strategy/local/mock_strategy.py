"""Strategy local: robot mock (sin hardware)."""

import asyncio
import logging
from typing import Any, override

from ..base import LocalStrategy
from ...robot.robot_mock_controller import RobotMockController
from ...rosbridge.json_rpc import (
    JsonRpcCommand, JsonRpcResponse, handle_json_rpc, create_status_notification,
)

logger = logging.getLogger(__name__)

_STATUS_INTERVAL_SEC = 5.0


class MockStrategy(LocalStrategy):
    """Wrappea RobotMockController para implementar la interfaz Strategy.

    Mismo comportamiento que SerialStrategy pero sin hardware.
    """

    def __init__(self, arduino_port: str):
        self._robot = RobotMockController(arduino_port)
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._telemetry_enabled: bool = True
        self._telemetry_task: asyncio.Task | None = None

    @property
    @override
    def status(self) -> str:
        telemetry = "on" if self._telemetry_enabled else "off"
        return f"running, telemetry: {telemetry}"

    @override
    def set_telemetry(self, enabled: bool) -> None:
        self._telemetry_enabled = enabled
        if enabled and (self._telemetry_task is None or self._telemetry_task.done()):
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        elif not enabled and self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
            self._telemetry_task = None
        logger.info("Telemetría mock %s", "habilitada" if enabled else "deshabilitada")

    @override
    async def start(self) -> None:
        self._robot.connect()
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        logger.info("MockStrategy iniciado")

    @override
    async def stop(self) -> None:
        if self._telemetry_task and not self._telemetry_task.done():
            self._telemetry_task.cancel()
        self._robot.disconnect()
        logger.info("MockStrategy detenido")

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
        """Recibe un comando en formato interno, lo ejecuta en el mock."""
        command = JsonRpcCommand.model_validate(message)
        response: JsonRpcResponse = await handle_json_rpc(command, self._robot)
        await self._outbox.put(response.model_dump(mode="json"))
