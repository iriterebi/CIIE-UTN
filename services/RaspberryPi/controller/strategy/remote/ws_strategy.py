"""Strategy remoto: conexión directa a la API via WebSocket.

Gestiona sus propias credenciales (registro + handshake HTTP con la API)
y se conecta al endpoint WS /m2m/robot/connect. Los mensajes son
JSON-RPC 2.0 directo — sin protocolo rosbridge de por medio.
"""

import asyncio
import json
import logging
from typing import Any, override

from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidURI

from pydantic import ValidationError

from ..base import Strategy, State
from ...server.server_service import ServerServices, RobotCredentials
from ...rosbridge.json_rpc import parse_command, _error_response

logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


def _derive_ws_url(server_url: str) -> str:
    """Deriva la URL del WebSocket a partir de la URL HTTP del servidor.

    http://host/m2m/robot/  → ws://host/m2m/robot/connect
    https://host/m2m/robot/ → wss://host/m2m/robot/connect
    """
    url = server_url.rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url + "/connect"


class WsStrategy(Strategy):
    """Conecta a la API como strategy remoto via WebSocket directo.

    start() ejecuta registro + handshake HTTP y conecta al WS de la API.
    receive() entrega comandos JSON-RPC recibidos del WS.
    send() envía respuestas/notificaciones JSON-RPC por el WS.
    """

    def __init__(
        self,
        *,
        server_url: str,
        metadata_file: str,
        create_default_metadata: bool = False,
    ):
        self._ws_url: str = _derive_ws_url(server_url)
        self._server_service: ServerServices = ServerServices(
            base_url=server_url,
            metadata_file=metadata_file,
            create_default_config=create_default_metadata,
        )
        self._ws: ClientConnection | None = None
        self._credentials: RobotCredentials | None = None

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)

        await self._connect_ws()
        self._state = State.RUNNING
        logger.info("WsStrategy iniciado (ws: %s)", self._ws_url)

    @override
    async def stop(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._state = State.STOPPED
        logger.info("WsStrategy detenido")

    @override
    async def receive(self) -> Any:
        """Escucha comandos JSON-RPC del WS de la API."""
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                async for raw in self._ws:  # type: ignore[union-attr]  # pyright: ignore[reportOptionalIterable]
                    delay = _MIN_RECONNECT_DELAY
                    msg = self._parse_message(raw)
                    if msg is not None:
                        return msg

            except ConnectionClosed:
                logger.warning(
                    "Conexión WS perdida, reconectando en %.1fs...", delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)
                try:
                    await self._reconnect()
                    logger.info("Reconectado al WS de la API")
                except (OSError, InvalidURI, ConnectionError) as e:
                    logger.error("Error reconectando: %s", e)

    @override
    async def send(self, message: Any) -> None:
        """Envía un mensaje JSON-RPC por el WS (sin wrapping rosbridge)."""
        try:
            await self._ws.send(json.dumps(message))  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
        except ConnectionClosed:
            logger.warning("No se pudo enviar mensaje (conexión perdida)")

    # --- Internos ---

    def _authenticate(self) -> None:
        """Ejecuta registro + handshake HTTP (sync). Bloquea hasta ser aprobado."""
        self._server_service.load_config()
        if not self._server_service.connect_with_retry():
            raise EnvironmentError("No se pudo establecer conexión con el servidor.")
        self._credentials = self._server_service.credentials

    async def _connect_ws(self) -> None:
        """Conecta al WS de la API y completa el handshake de autenticación."""
        self._ws = await connect(self._ws_url)

        # Recibir challenge del servidor
        challenge_raw = await self._ws.recv()
        challenge = json.loads(challenge_raw)
        if challenge.get("method") != "send_credentials":
            raise ConnectionError(
                f"Challenge inesperado del servidor: {challenge}"
            )

        # Enviar token JWT
        assert self._credentials is not None
        token = self._credentials.access_token.access_token
        await self._ws.send(json.dumps({"token": token}))

        # Esperar confirmación
        result_raw = await self._ws.recv()
        result = json.loads(result_raw)
        if result.get("status") != "success auth":
            raise ConnectionError(
                f"Auth WS fallido: {result}"
            )

        logger.info("Auth WS exitoso")

    async def _reconnect(self) -> None:
        """Re-autentica (JWT puede haber expirado) y reconecta al WS."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)
        await self._connect_ws()

    def _parse_message(self, raw: Any) -> dict[str, Any] | None:
        """Parsea un mensaje WS como comando JSON-RPC.

        Retorna el comando como dict, o None si no es parseable.
        """
        try:
            data = raw if isinstance(raw, str) else json.dumps(raw)
            command = parse_command(data)
            logger.info("Comando recibido: %s", command.method)
            return command.model_dump(mode="json")

        except ValidationError as e:
            logger.warning("Comando JSON-RPC inválido: %s", e)
            return _error_response(None, -32600, "Comando inválido").model_dump(mode="json")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Mensaje no parseable: %s", e)
            return None
