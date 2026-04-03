from abc import ABC, abstractmethod
from typing import Any, Never, Protocol, final, override
import asyncio
import logging
from ..entities import Robot
from ...auth.entities import User


logger = logging.getLogger(__name__)

class OnMessageCallback(Protocol):
    async def __call__(self, data: Any) -> None: ...  # pyright: ignore[reportExplicitAny, reportAny]

class StreamSource(Protocol):
    """Polimórfico con WebSocket.

    Método opcional:
        async def on_idle_changed(self, idle: bool): ...
            Notifica al source que la conexión pasó a idle (True) o dejó de estarlo (False).
            Se invoca via hasattr desde RobotConnection. Útil para manejar backpressure
            (ej: dejar de llenar la queue cuando no hay lectores).
    """
    async def accept(self): ...
    async def disconnect(self): ...
    # TODO: receive_bytes debe ser un iterador
    async def receive_data(self) -> Any: ...
    async def send_data(self, data: Any) -> None: ...  # pyright: ignore[reportExplicitAny, reportAny]

class StreamConnection(ABC):
    def __init__(self, ws: StreamSource):
        self.ws: StreamSource = ws
        self._onMessageCallbacks: list[OnMessageCallback] = []

    def on(self, callback: OnMessageCallback):
        self._onMessageCallbacks.append(callback)

    async def connect(self)-> Never:
        await self.ws.accept()
        try:
            while True:
                try:
                    message = await self.ws.receive_data()
                    await self._onMessage(message)
                except Exception as e:
                    logger.error(f"StreamConnection error: {e}")
                    raise
        finally:
            await self._on_disconnect()

    @abstractmethod
    async def _on_disconnect(self):
        """Cleanup al terminar la conexión. Cada subclase define su comportamiento."""
        ...

    async def _onMessage(self, message: Any):
        for callback in self._onMessageCallbacks:
            await callback(message)

    async def send(self, data: Any):  # pyright: ignore[reportExplicitAny, reportAny]
        await self.ws.send_data(data)

    async def disconnect(self):
        await self.ws.disconnect()


class RobotConnection(StreamConnection):
    def __init__(self, ws: StreamSource, robot: Robot):
        super().__init__(ws)
        self.robot: Robot = robot
        self._idle: bool = True

    @property
    def idle(self) -> bool:
        return self._idle

    @override
    async def connect(self):
        self._idle = False
        if hasattr(self.ws, 'on_idle_changed'):
            await self.ws.on_idle_changed(False)
        await super().connect()

    @override
    async def _on_disconnect(self):
        self._idle = True
        if hasattr(self.ws, 'on_idle_changed'):
            await self.ws.on_idle_changed(True)

@final
class UserConnection(StreamConnection):
    def __init__(self, ws: StreamSource, user: User):
        super().__init__(ws)
        self.user = user

    @override
    async def _on_disconnect(self):
        await self.disconnect()

@final
class UsersXRobotMapType:
    def __init__(self, user: UserConnection, robot: RobotConnection):
        self.user = user
        self.robot = robot
        self._tasks: list[asyncio.Task[Never]] = []

    @property
    def connected(self) -> bool:
        return len(self._tasks) > 0

    async def connect(self):
        self.user.on(self.robot.send)
        self.robot.on(self.user.send)

        async with asyncio.TaskGroup() as tg:
            self._tasks = [
                tg.create_task(self.user.connect()),
                tg.create_task(self.robot.connect()),
            ]

    def disconnect(self):
        for task in self._tasks:
            _ = task.cancel()
        self._tasks = []
