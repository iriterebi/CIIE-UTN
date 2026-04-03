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
    def __init__(self, websocket: WebSocket):
        self.websocket: WebSocket = websocket

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
                command = RRobotCommand.model_validate_json(text)
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
        await self.websocket.send_json(data)
