import logging
from typing import Any, override

from fastapi.websockets import WebSocket, WebSocketState

from ..repositories.robot_connection import StreamSource


logger = logging.getLogger(__name__)


class RobotWsStreamSource(StreamSource):
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
        return await self.websocket.receive_json()  # pyright: ignore[reportAny]

    @override
    async def send_data(self, data: Any):
        await self.websocket.send_json(data)


