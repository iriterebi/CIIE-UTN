import asyncio
import json
import logging
from typing import Any, override

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketState

from ..entities.json_rpc_commands import RRobotCommand
from ..repositories.robot_connection import StreamSource


logger = logging.getLogger(__name__)


class UserStreamSource(StreamSource):
    # TODO: manejar cuestiones relacionadas a la sesión del usuario (ejemplo: expiración)
    # TODO: validación profunda del payload — ampliar más allá de RRobotCommand
    # TODO: verificación del access_token per-sesión
    def __init__(self, websocket: WebSocket, *, pong_received: asyncio.Event | None = None):
        self.websocket: WebSocket = websocket
        self.pong_received: asyncio.Event = pong_received if pong_received is not None else asyncio.Event()
        self._send_lock: asyncio.Lock = asyncio.Lock()

    @override
    async def accept(self):
        if self.websocket.application_state != WebSocketState.CONNECTED:
            return await self.websocket.accept()

    @override
    async def disconnect(self):
        return await self.websocket.close()

    @override
    async def receive_data(self) -> Any:
        while True:
            try:
                text = await self.websocket.receive_text()
                logger.info(f"Received text from user: {text}")
                data = json.loads(text)
                if isinstance(data, dict) and data.get("type") == "pong":
                    self.pong_received.set()
                    continue
                command = RRobotCommand.model_validate(data)
                return command.model_dump(mode="python")
            except ValidationError as e:
                logger.error(f"Payload validation error: {e}")
                await self.websocket.send_json({
                    "status": "error",
                    "message": f"Invalid payload: {e.errors()}"
                })
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                await self.websocket.send_json({
                    "status": "error",
                    "message": f"Invalid JSON: {e}"
                })

    @override
    async def send_data(self, data: Any) -> None:  # pyright: ignore[reportAny, reportExplicitAny]
        async with self._send_lock:
            await self.websocket.send_json(data)

    async def send_control(self, data: dict) -> None:
        """Envía un frame de control (ej. heartbeat ping) usando el mismo
        lock que `send_data`, para no intercalar escrituras concurrentes
        sobre el mismo WebSocket físico.
        """
        async with self._send_lock:
            await self.websocket.send_json(data)
