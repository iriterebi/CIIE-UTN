import asyncio
import logging
from typing import Any, override

from fastapi.websockets import WebSocket, WebSocketState

from ..entities import Robot
from ..repositories.robot_connection import StreamSource
from ..services.rosbridge_client import RosBridgeClient


logger = logging.getLogger(__name__)


class RobotScopedStreamSource(StreamSource):
    def __init__(self, rosbridge: RosBridgeClient, robot: Robot):
        self.rosbridge: RosBridgeClient = rosbridge
        self.robot: Robot = robot
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._idle: bool = True

    @override
    async def accept(self):
        """Suscribirse a los topics ROS del robot via rosbridge."""
        await self.rosbridge.subscribe_robot(self.robot, self.queue)

    @override
    async def disconnect(self):
        """Desuscribirse de los topics ROS del robot."""
        await self.rosbridge.unsubscribe_robot(self.robot, self.queue)

    async def on_idle_changed(self, idle: bool):
        self._idle = idle
        if idle:
            await self.disconnect()

            # Descartar mensajes acumulados que nadie va a leer
            while not self.queue.empty():
                _ = self.queue.get_nowait()
        else:
            await self.accept()

    @override
    async def receive_data(self) -> Any:
        """Esperar respuesta del robot desde ROS, retornar como bytes."""
        return await self.queue.get()

    @override
    async def send_data(self, data: Any):
        """Publicar comando al topic ROS del robot via rosbridge."""
        await self.rosbridge.publish_command(self.robot, data)


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


