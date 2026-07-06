from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Coroutine, Never, Protocol, final, override
import asyncio
import logging
from ..entities import Robot
from ...auth.entities import User


logger = logging.getLogger(__name__)

_ROBOT_RECONNECT_WAIT_SECONDS: float = 120.0


class UserSideClosed(Exception):
    """La conexión del lado usuario del pipe terminó (cierre normal o error)."""


class RobotSideClosed(Exception):
    """La conexión del lado robot del pipe terminó sin reconectar a tiempo."""


async def _wrap_side(coro: Coroutine[Any, Any, Never], wrapper: type[Exception]) -> Never:
    """Envuelve excepciones de un lado del pipe para discriminar el origen.

    Solo se envuelve `Exception`: `CancelledError` (BaseException) se deja pasar
    sin tocar para que `TaskGroup` la reconozca como cancelación interna y la
    filtre del `ExceptionGroup` final.
    """
    try:
        await coro
    except Exception as e:
        raise wrapper() from e
    raise AssertionError("unreachable")

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


type RemoveListener = Callable[[], None]

class StreamConnection(ABC):
    def __init__(self, ws: StreamSource):
        self.ws: StreamSource = ws
        self._onMessageCallbacks: list[OnMessageCallback] = []

    def on(self, callback: OnMessageCallback) -> RemoveListener:
        self._onMessageCallbacks.append(callback)

        return lambda : self._onMessageCallbacks.remove(callback)


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
        self._disconnectables: list[RemoveListener] = []
        # Tarea que corre `connect()` (el "padre" del TaskGroup interno).
        # Necesaria porque `disconnect()` puede invocarse desde otra tarea
        # mientras `connect()` sigue corriendo: cancelar directamente las
        # tareas hijas (`self._tasks`) no alcanza, ya que `TaskGroup`
        # ignora cancelaciones externas de sus hijos si la propia tarea
        # padre nunca fue cancelada (ver `asyncio.taskgroups._on_task_done`,
        # que hace `if task.cancelled(): return` sin registrar error ni
        # abortar al resto) — el grupo terminaría sin excepción alguna.
        # Cancelar la tarea padre sí dispara el camino normal de
        # cancelación de `TaskGroup._aexit`.
        self._connect_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        return len(self._tasks) > 0

    def _bind_robot_listeners(self) -> None:
        for remove in self._disconnectables:
            remove()
        self._disconnectables = [
            self.user.on(self.robot.send),
            self.robot.on(self.user.send),
        ]

    async def _supervise_robot(
        self,
        wait_for_robot_reconnect: Callable[[str, float], Awaitable[RobotConnection | None]],
        reconnect_timeout: float,
    ) -> Never:
        """Corre `self.robot.connect()` en loop, sobreviviendo a caídas.

        Si el robot se cae, notifica al usuario y espera a que
        `wait_for_robot_reconnect` devuelva una nueva `RobotConnection`.
        Si llega a tiempo, se re-vincula (`self.robot = new_robot`) y
        se reintenta. Si se agota el timeout, levanta `RobotSideClosed`
        — recién ahí termina también el lado usuario (vía TaskGroup).
        """
        while True:
            try:
                await self.robot.connect()
            except Exception as e:
                robot_id = str(self.robot.robot.id)

                await self.user.send({
                    "status": "robot_disconnected",
                    "message": "robot desconectado, reconectando...",
                })

                new_robot = await wait_for_robot_reconnect(robot_id, reconnect_timeout)

                if new_robot is None:
                    await self.user.send({
                        "status": "robot_unavailable",
                        "message": "el robot no reconectó a tiempo",
                    })
                    raise RobotSideClosed() from e

                self.robot = new_robot
                self._bind_robot_listeners()
                await self.user.send({"status": "robot_reconnected"})
                continue

            # `RobotConnection.connect()` está anotado `Never`: no debería
            # retornar. Si algún día lo hace, no dejamos el supervisor
            # colgado en silencio.
            raise AssertionError("unreachable: RobotConnection.connect() no debería retornar")

    async def connect(
        self,
        *,
        wait_for_robot_reconnect: Callable[[str, float], Awaitable[RobotConnection | None]],
        reconnect_timeout: float = _ROBOT_RECONNECT_WAIT_SECONDS,
    ) -> None:
        self._bind_robot_listeners()
        self._connect_task = asyncio.current_task()

        try:
            async with asyncio.TaskGroup() as tg:
                self._tasks = [
                    tg.create_task(_wrap_side(self.user.connect(), UserSideClosed)),
                    tg.create_task(self._supervise_robot(wait_for_robot_reconnect, reconnect_timeout)),
                ]
        finally:
            self._connect_task = None

    def disconnect(self):
        if self._connect_task is not None:
            _ = self._connect_task.cancel()

        for task in self._tasks:
            _ = task.cancel()

        for func in self._disconnectables:
            try:
                func()
            except Exception:
                logger.warning("Listener cleanup raised", exc_info=True)

        self._tasks = []
        self._disconnectables = []
