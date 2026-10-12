"""Cliente WS dedicado a video: empuja frames JPEG de CameraRelay a la Api.

Canal separado de WsStrategy/MicroCore (ver
docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md):
push-only, binario, no pasa por el pipe JSON-RPC. Gestiona sus propias
credenciales con su propia instancia de ServerServices — no reutiliza la
de WsStrategy (ver ARQUITECTURA.md: "Cada strategy debe pedir sus propias
credenciales").
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Never

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidURI

from ..server.server_service import ServerServices

logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


def derive_video_ws_url(server_url: str) -> str:
    """Deriva la URL del WS de video a partir de la URL HTTP del servidor.

    http://host/m2m/robot/  → ws://host/m2m/robot/video
    https://host/m2m/robot/ → wss://host/m2m/robot/video

    Mismo esquema que `ws_strategy._derive_ws_url`, pero apuntando a
    `/video` en vez de `/connect`.
    """
    url = server_url.rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url + "/video"


class VideoWsClient:
    def __init__(self, *, server_service: ServerServices, ws_url: str):
        self._server_service = server_service
        self._ws_url = ws_url
        self._ws: ClientConnection | None = None

    async def run(self, next_frame: Callable[[], Awaitable[bytes]]) -> Never:
        """Conecta, reenvía cada frame de `next_frame()`, reconecta ante corte.

        Igual que `WsStrategy.receive`: nunca retorna, el reintento vive
        adentro. Un frame que falla al enviarse (conexión caída) se
        descarta — coherente con "último frame gana", no se bufferiza.
        """
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                await self._connect()
                delay = _MIN_RECONNECT_DELAY
                while True:
                    frame = await next_frame()
                    assert self._ws is not None
                    await self._ws.send(frame)
            except (ConnectionClosed, ConnectionError, OSError, InvalidURI) as e:
                logger.warning(
                    "VideoWsClient: conexión perdida (%s), reconectando en %.1fs...",
                    e, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _connect(self) -> None:
        await self._authenticate()

        self._ws = await connect(self._ws_url)

        challenge_raw = await self._ws.recv()
        challenge: Any = json.loads(challenge_raw)
        if challenge.get("method") != "send_credentials":
            raise ConnectionError(f"Challenge inesperado del servidor: {challenge}")

        assert self._server_service.credentials is not None
        token = self._server_service.credentials.access_token.access_token
        await self._ws.send(json.dumps({"token": token}))

        result_raw = await self._ws.recv()
        result: Any = json.loads(result_raw)
        if result.get("status") != "success auth":
            raise ConnectionError(f"Auth WS de video fallido: {result}")

        logger.info("VideoWsClient: auth WS exitoso")

    async def _authenticate(self) -> None:
        """Ejecuta registro + handshake HTTP. Espera hasta ser aprobado (cancelable)."""
        await asyncio.to_thread(self._server_service.load_config)
        if not await self._server_service.connect_with_retry():
            raise OSError("VideoWsClient: no se pudo autenticar con el servidor.")
