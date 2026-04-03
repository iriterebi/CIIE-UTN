import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, override

from ..repositories.robot_connection import StreamSource


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

    async def enqueue_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.queue.put(data)

    async def clean_queue(self):
        while not self.queue.empty():
            _ = self.queue.get_nowait()

    async def on_idle_changed(self, idle: bool):
        return await self.on_idle_changed_callback(idle)

    @override
    async def accept(self):
        return await self.on_accept()

    @override
    async def disconnect(self):
        return await self.on_disconnect()

    @override
    async def receive_data(self) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
        return await self.queue.get()  # pyright: ignore[reportAny]

    @override
    async def send_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.on_recieve(data)
