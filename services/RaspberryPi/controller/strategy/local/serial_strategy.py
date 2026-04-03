"""Strategy local: comunicación serial con Arduino."""

import asyncio
import logging
from typing import Any, override

from ..base import Strategy
from ...robot.robot_controller import RobotController
from ...rosbridge.json_rpc import (
    JsonRpcCommand, JsonRpcResponse, handle_json_rpc, create_status_notification,
)

logger = logging.getLogger(__name__)

_STATUS_INTERVAL_SEC = 5.0


class SerialStrategy(Strategy):
    """Wrappea RobotController para implementar la interfaz Strategy.

    Traduce comandos JSON-RPC (formato interno) a operaciones serial
    y produce respuestas + status periódico.
    """

    def __init__(self, arduino_port: str):
        self._robot = RobotController(arduino_port)
        self._outbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)
        logger.info("SerialStrategy iniciado (puerto: %s)", self._robot.arduino_port)

    @override
    async def stop(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.disconnect)
        logger.info("SerialStrategy detenido")

    @override
    async def receive(self) -> Any:
        """Retorna el próximo mensaje saliente (respuesta o status).

        Produce status periódico cuando no hay respuestas pendientes.
        """
        try:
            return await asyncio.wait_for(self._outbox.get(), timeout=_STATUS_INTERVAL_SEC)
        except TimeoutError:
            notification = create_status_notification(self._robot.get_status())
            return notification.model_dump(mode="json")

    @override
    async def send(self, message: Any) -> None:
        """Recibe un comando en formato interno, lo ejecuta en el robot."""
        command = JsonRpcCommand.model_validate(message)
        response: JsonRpcResponse = await handle_json_rpc(command, self._robot)
        await self._outbox.put(response.model_dump(mode="json"))
