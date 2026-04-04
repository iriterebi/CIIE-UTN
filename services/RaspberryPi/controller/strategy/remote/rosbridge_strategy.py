"""Strategy remoto: comunicación con rosbridge via WebSocket.

Gestiona sus propias credenciales (registro + handshake con la API)
y traduce entre formato interno (JSON-RPC dicts) y protocolo rosbridge
(std_msgs/String wrapping, ops subscribe/publish).
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


class RosbridgeStrategy(Strategy):
    """Conecta a rosbridge como strategy remoto.

    start() ejecuta registro + handshake y conecta al WS de rosbridge.
    receive() entrega comandos traducidos a formato interno.
    send() traduce formato interno a protocolo rosbridge y publica.
    """

    def __init__(
        self,
        *,
        server_url: str,
        rosbridge_url: str,
        metadata_file: str,
        create_default_metadata: bool = False,
    ):
        self._rosbridge_url: str = rosbridge_url
        self._server_service: ServerServices = ServerServices(
            base_url=server_url,
            metadata_file=metadata_file,
            create_default_config=create_default_metadata,
        )
        self._ws: ClientConnection | None = None
        self._credentials: RobotCredentials | None = None
        self._inbox: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        self._topic_command: str = ""
        self._topic_response: str = ""
        self._topic_status: str = ""

    @override
    async def start(self) -> None:
        # Registro y handshake (sync, en executor para no bloquear)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)

        assert self._credentials is not None
        self._topic_command = f"{self._credentials.topic}/command"
        self._topic_response = f"{self._credentials.topic}/response"
        self._topic_status = f"{self._credentials.topic}/status"

        # Conectar a rosbridge
        await self._connect_rosbridge()
        self._state = State.RUNNING
        logger.info("RosbridgeStrategy iniciado (topics: %s)", self._credentials.topic)

    @override
    async def stop(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._state = State.STOPPED
        logger.info("RosbridgeStrategy detenido")

    @override
    async def receive(self) -> Any:
        """Escucha comandos de rosbridge y los entrega en formato interno."""
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                async for raw in self._ws:  # type: ignore[union-attr]
                    delay = _MIN_RECONNECT_DELAY
                    msg = self._parse_rosbridge_message(raw)
                    if msg is not None:
                        return msg

            except ConnectionClosed:
                logger.warning(
                    "Conexión a rosbridge perdida, reconectando en %.1fs...", delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)
                try:
                    await self._connect_rosbridge()
                    logger.info("Reconectado a rosbridge")
                except (OSError, InvalidURI) as e:
                    logger.error("Error reconectando: %s", e)

    @override
    async def send(self, message: Any) -> None:
        """Traduce formato interno a protocolo rosbridge y publica.

        Determina el topic según el tipo de mensaje:
        - Si tiene 'result' o 'error' → response
        - Si tiene 'method' (notification) → status
        """
        if "result" in message or "error" in message:
            topic = self._topic_response
        else:
            topic = self._topic_status

        rosbridge_msg = {
            "op": "publish",
            "topic": topic,
            "msg": {"data": json.dumps(message)},
        }
        try:
            await self._ws.send(json.dumps(rosbridge_msg))  # type: ignore[union-attr]
        except ConnectionClosed:
            logger.warning("No se pudo enviar mensaje (conexión perdida)")

    # --- Internos ---

    def _authenticate(self) -> None:
        """Ejecuta registro + handshake (sync). Bloquea hasta ser aprobado."""
        self._server_service.load_config()
        if not self._server_service.connect_with_retry():
            raise EnvironmentError("No se pudo establecer conexión con el servidor.")
        self._credentials = self._server_service.credentials

    async def _connect_rosbridge(self) -> None:
        """Conecta al WS de rosbridge, advierte topics y subscribe comandos."""
        self._ws = await connect(self._rosbridge_url)
        await self._advertise_topics()
        await self._subscribe_commands()

    def _parse_rosbridge_message(self, raw: Any) -> dict[str, Any] | None:
        """Traduce un mensaje de rosbridge a formato interno.

        Retorna None si no es un comando válido para este robot.
        """
        try:
            msg = json.loads(raw) if isinstance(raw, str) else raw
            topic = msg.get("topic", "")
            if topic != self._topic_command:
                return None

            data = msg.get("msg", {}).get("data", "{}")
            command = parse_command(data)
            logger.info("Comando recibido: %s", command.method)
            return command.model_dump(mode="json")

        except ValidationError as e:
            logger.warning("Comando JSON-RPC inválido: %s", e)
            return _error_response(None, -32600, "Comando inválido").model_dump(mode="json")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Mensaje no parseable: %s", e)
            return None

    async def _advertise_topics(self) -> None:
        for topic in (self._topic_response, self._topic_status):
            msg = {
                "op": "advertise",
                "topic": topic,
                "type": "std_msgs/String",
            }
            await self._ws.send(json.dumps(msg))  # type: ignore[union-attr]
        await asyncio.sleep(0.5)
        logger.info("Topics advertised: %s, %s", self._topic_response, self._topic_status)

    async def _subscribe_commands(self) -> None:
        msg = {
            "op": "subscribe",
            "topic": self._topic_command,
            "type": "std_msgs/String",
        }
        await self._ws.send(json.dumps(msg))  # type: ignore[union-attr]
        logger.info("Suscrito a %s", self._topic_command)
