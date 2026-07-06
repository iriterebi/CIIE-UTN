import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, override

from ..repositories.robot_connection import StreamSource


class ProxyStreamDisconnected(Exception):
    """La conexión física (WS de la Pi) terminó — `reason` es `"clean_close"` o `"timeout"`."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Physical robot connection ended: {reason}")
        self.reason: str = reason


class ProxyStreamSource(StreamSource):
    def __init__(self, *,
        on_recieve: Callable[[Any], Awaitable[None]],  # pyright: ignore[reportExplicitAny]
        on_disconnect: Callable[[], Awaitable[None]],
        on_accept: Callable[[], Awaitable[None]],
        on_idle_changed: Callable[[bool], Awaitable[None]],
    ):
        self.on_recieve: Callable[[Any], Awaitable[None]] = on_recieve  # pyright: ignore[reportExplicitAny]
        self.on_disconnect: Callable[[], Awaitable[None]] = on_disconnect
        self.on_accept: Callable[[], Awaitable[None]] = on_accept
        self.on_idle_changed_callback: Callable[[bool], Awaitable[None]] = on_idle_changed
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)  # pyright: ignore[reportExplicitAny]
        self._disconnect_event: asyncio.Event = asyncio.Event()
        self._disconnected_exc: ProxyStreamDisconnected | None = None

    async def enqueue_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.queue.put(data)

    async def clean_queue(self):
        while not self.queue.empty():
            _ = self.queue.get_nowait()

    async def on_idle_changed(self, idle: bool):
        return await self.on_idle_changed_callback(idle)

    async def mark_disconnected(self, reason: str) -> None:
        """Marca la conexión física como muerta.

        Cualquier `receive_data()` pendiente o futuro levanta
        `ProxyStreamDisconnected(reason)`. Idempotente: si ya estaba
        marcada, conserva el motivo original.
        """
        if self._disconnected_exc is None:
            self._disconnected_exc = ProxyStreamDisconnected(reason)
        self._disconnect_event.set()

    @override
    async def accept(self):
        return await self.on_accept()

    @override
    async def disconnect(self):
        return await self.on_disconnect()

    @override
    async def receive_data(self) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
        if self._disconnected_exc is not None:
            raise self._disconnected_exc

        get_task = asyncio.ensure_future(self.queue.get())
        disconnect_task = asyncio.ensure_future(self._disconnect_event.wait())
        try:
            done, pending = await asyncio.wait(
                {get_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except BaseException:
            get_task.cancel()
            disconnect_task.cancel()
            raise
        else:
            for task in pending:
                _ = task.cancel()

        if get_task in done:
            return get_task.result()  # pyright: ignore[reportAny]

        assert self._disconnected_exc is not None
        raise self._disconnected_exc

    @override
    async def send_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.on_recieve(data)
