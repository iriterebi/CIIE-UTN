"""Relay de video 1:1 por robot: último frame gana.

Ver docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
No es un StreamSource/StreamConnection (esos existen para el pipe JSON-RPC
de comandos, ver stream_entities.py): es un canal push-only, sin heartbeat
ni reconexión propia — cada lado (Pi, browser) maneja su propia reconexión
física de forma independiente.
"""

import asyncio
import functools
from typing import Annotated

from fastapi import Depends


class VideoRelay:
    """Cola de capacidad 1: pisa el frame anterior si nadie lo consumió."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)

    def push_frame(self, frame: bytes) -> None:
        if self._queue.full():
            _ = self._queue.get_nowait()
        self._queue.put_nowait(frame)

    async def next_frame(self) -> bytes:
        return await self._queue.get()


class VideoRelayRepository:
    def __init__(self) -> None:
        self._relays: dict[str, VideoRelay] = {}

    def get_or_create(self, robot_id: str) -> VideoRelay:
        if robot_id not in self._relays:
            self._relays[robot_id] = VideoRelay()
        return self._relays[robot_id]

    def discard(self, robot_id: str) -> None:
        _ = self._relays.pop(robot_id, None)


@functools.cache
def get_video_relay_repository() -> VideoRelayRepository:
    return VideoRelayRepository()


VideoRelayRepositoryDep = Annotated[VideoRelayRepository, Depends(get_video_relay_repository)]
