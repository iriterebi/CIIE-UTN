"""Strategy local: robot mock (sin hardware)."""

import asyncio
import logging
from typing import Any, override

from ..base import Strategy
from ...robot.robot_mock_controller import RobotMockController
from ...rosbridge.json_rpc import (
    JsonRpcCommand, JsonRpcResponse, handle_json_rpc, create_status_notification,
)

logger = logging.getLogger(__name__)

_STATUS_INTERVAL_SEC = 5.0


class MockStrategy(Strategy):
    """Wrappea RobotMockController para implementar la interfaz Strategy.

    Mismo comportamiento que SerialStrategy pero sin hardware.
    """

    def __init__(self, arduino_port: str):
        self._robot = RobotMockController(arduino_port)
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @override
    async def start(self) -> None:
        self._robot.connect()
        logger.info("MockStrategy iniciado")

    @override
    async def stop(self) -> None:
        self._robot.disconnect()
        logger.info("MockStrategy detenido")

    @override
    async def receive(self) -> Any:
        """Retorna el próximo mensaje saliente (respuesta o status)."""
        try:
            return await asyncio.wait_for(self._outbox.get(), timeout=_STATUS_INTERVAL_SEC)
        except TimeoutError:
            notification = create_status_notification(self._robot.get_status())
            return notification.model_dump(mode="json")

    @override
    async def send(self, message: Any) -> None:
        """Recibe un comando en formato interno, lo ejecuta en el mock."""
        command = JsonRpcCommand.model_validate(message)
        response: JsonRpcResponse = await handle_json_rpc(command, self._robot)
        await self._outbox.put(response.model_dump(mode="json"))
