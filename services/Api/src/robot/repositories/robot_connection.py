
from abc import ABC, abstractmethod
from typing import Never, Protocol, Annotated, final, override
from fastapi import Depends
import asyncio
import functools
import logging
from ..entities import Robot
from ...auth.entities import User


logger = logging.getLogger(__name__)

class OnMessageCallback(Protocol):
    async def __call__(self, data: bytes) -> None: ...

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
    async def receive_bytes(self) -> bytes: ...
    async def send_bytes(self, data: bytes): ...

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
                    message = await self.ws.receive_bytes()
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

    async def _onMessage(self, message: bytes):
        for callback in self._onMessageCallbacks:
            await callback(message)

    async def send(self, data: bytes):
        await self.ws.send_bytes(data)

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

class RobotConnectionRepository:
    def __init__(self):
        self._robots: dict[str, RobotConnection] = {}
        self._users: dict[str, UserConnection] = {}
        self._users_x_robot: list[UsersXRobotMapType] = []

    def addRobotConnection(self, robot: Robot, streamSource: StreamSource) -> RobotConnection:
        if robot.id in self._robots:
            raise ValueError("Robot already connected")

        self._robots[robot.id] = RobotConnection(streamSource, robot)
        return self._robots[robot.id]

    def addUserConnection(self, user: User, streamSource: StreamSource) -> UserConnection:
        if user.id in self._users:
            raise ValueError("User already connected")

        self._users[user.id] = UserConnection(streamSource, user)
        return self._users[user.id]

    def getRobotConnection(self, robot: Robot | str) -> RobotConnection | None:
        if isinstance(robot, Robot):
            robot = robot.id

        return self._robots.get(robot)

    def getUserConnection(self, user: User | str) -> UserConnection | None:
        if isinstance(user, User):
            user = user.id

        return self._users.get(user)

    def discardUserConnection(self, userOrConnection: UserConnection | User | str, *, discardPipeddConnections: bool = False):
        if isinstance(userOrConnection, UserConnection):
            userOrConnection = userOrConnection.user.id

        if isinstance(userOrConnection, User):
            userOrConnection = userOrConnection.id

        if userOrConnection not in self._users:
            raise ValueError("User not found")

        if (connection := self.getUserXRobotConnection(user=userOrConnection)):
            self.discardUserXRobotConnection(connection, disconnect=discardPipeddConnections)

        del self._users[userOrConnection]

    def discardRobotConnection(self, robotOrConnection: RobotConnection | Robot | str, *, discardPipeddConnections: bool = False):
        if isinstance(robotOrConnection, RobotConnection):
            robotOrConnection = robotOrConnection.robot.id

        if isinstance(robotOrConnection, Robot):
            robotOrConnection = robotOrConnection.id

        if robotOrConnection not in self._robots:
            raise ValueError("Robot not found")

        if (connection := self.getUserXRobotConnection(robot=robotOrConnection)):
            self.discardUserXRobotConnection(connection, disconnect=discardPipeddConnections)


        del self._robots[robotOrConnection]

    def getUserXRobotConnection(self, *, user: User | str | None = None, robot: Robot | str | None = None) -> UsersXRobotMapType | None:
        userConnection = self.getUserConnection(user) if user is not None else None
        robotConnection = self.getRobotConnection(robot) if robot is not None else None

        if userConnection is not None and robotConnection is not None:
            for connection in self._users_x_robot:
                if connection.user == userConnection and connection.robot == robotConnection:
                    return connection
        elif userConnection is not None:
            for connection in self._users_x_robot:
                if connection.user == userConnection:
                    return connection
        elif robotConnection is not None:
            for connection in self._users_x_robot:
                if connection.robot == robotConnection:
                    return connection

        return None

    def addUserXRobotConnection(self, userConnection: UserConnection, robotConnection: RobotConnection) -> UsersXRobotMapType:
        if self.getUserConnection(userConnection.user) is not userConnection:
            raise ValueError("User already connected")

        if self.getRobotConnection(robotConnection.robot) is not robotConnection:
            raise ValueError("Robot already connected")

        if (connection := self.getUserXRobotConnection(user=userConnection.user)) is not None:
            raise RobotInUseError(connection=connection)

        if (connection := self.getUserXRobotConnection(robot=robotConnection.robot)) is not None:
            raise RobotInUseError(connection=connection)

        connection = UsersXRobotMapType(user=userConnection, robot=robotConnection)
        self._users_x_robot.append(connection)
        return connection

    def discardUserXRobotConnection(self, connection: UsersXRobotMapType, *, disconnect: bool = False):
        if connection not in self._users_x_robot:
            raise ValueError("Connection not found")

        if connection.connected:
            if disconnect:
                connection.disconnect()
            else:
                raise RobotInUseError(connection)

        self._users_x_robot.remove(connection)


@functools.cache
def get_robot_connection_repository() -> RobotConnectionRepository:
    return RobotConnectionRepository()

RobotConnectionRepositoryDep = Annotated[RobotConnectionRepository, Depends(get_robot_connection_repository)]

class RobotInUseError(Exception):
    connection: UsersXRobotMapType

    def __init__(self, connection: UsersXRobotMapType):
        super().__init__("Robot already in use")
        self.connection = connection
