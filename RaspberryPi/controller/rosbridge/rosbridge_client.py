"""Cliente WebSocket para comunicación con rosbridge_suite.

Conecta la Pi directamente a rosbridge (ws://rosbridge:9090),
se suscribe al topic de comandos del robot y publica respuestas y estado.

TODO: Reemplazar por nodo ROS 2 real (rclpy) en el futuro.
"""

import asyncio
import json
import logging
from typing import Awaitable, Callable

from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidURI

from pydantic import ValidationError

from ..server.server_service import RobotCredentials
from .json_rpc import JsonRpcCommand, JsonRpcResponse, parse_command, _error_response, create_status_notification


logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0
_STATUS_INTERVAL_SEC = 5.0


class PiRosBridgeClient:
    """Cliente WebSocket que conecta un robot individual a rosbridge."""

    _topic_command: str
    _topic_response: str
    _topic_status: str

    def __init__(self, rosbridge_url: str, credentials: RobotCredentials):
        self._url = rosbridge_url
        self._ws: ClientConnection | None = None
        self._tasks: list[asyncio.Task] = []

        # Topics de este robot
        self._topic_command = f"{credentials.topic}/command"
        self._topic_response = f"{credentials.topic}/response"
        self._topic_status = f"{credentials.topic}/status"

        logger.info(
            "Topics configurados: command=%s, response=%s, status=%s",
            self._topic_command, self._topic_response, self._topic_status,
        )

    async def connect(self):
        """Conectar al rosbridge WebSocket."""
        self._ws = await connect(self._url)
        await self._advertise_topics()
        await self._subscribe_commands()
        logger.info("Conectado a rosbridge en %s", self._url)

    async def disconnect(self):
        """Cancelar tasks y cerrar conexión."""
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        if self._ws:
            await self._ws.close()
        logger.info("Desconectado de rosbridge")

    async def run(
        self,
        on_command: Callable[[JsonRpcCommand], Awaitable[JsonRpcResponse]],
        get_status: Callable[[], dict],
    ):
        """Loop principal: escucha comandos y publica estado periódico.

        Args:
            on_command: Callback async que recibe un JsonRpcCommand y retorna JsonRpcResponse.
            get_status: Callback sync que retorna el estado actual del robot.
        """
        listener = asyncio.create_task(self._listen(on_command))
        status_pub = asyncio.create_task(self._publish_status_loop(get_status))
        self._tasks = [listener, status_pub]

        try:
            # Esperar hasta que alguna task termine (por error o cancelación)
            done, _ = await asyncio.wait(
                self._tasks, return_when=asyncio.FIRST_EXCEPTION
            )
            for task in done:
                if task.exception():
                    raise task.exception()
        except asyncio.CancelledError:
            pass

    async def _listen(self, on_command: Callable[[JsonRpcCommand], Awaitable[JsonRpcResponse]]):
        """Recibe mensajes de rosbridge, procesa comandos y publica respuestas."""
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                async for raw in self._ws:
                    delay = _MIN_RECONNECT_DELAY
                    try:
                        msg = json.loads(raw)
                        topic = msg.get("topic", "")
                        if topic != self._topic_command:
                            continue

                        command = parse_command(msg.get("msg", {}).get("data", "{}"))

                        logger.info("Comando recibido: %s", command.method)

                        response = await on_command(command)
                        await self._publish(self._topic_response, response.model_dump(mode="json"))

                    except ValidationError as e:
                        logger.warning("Comando JSON-RPC inválido: %s", e)
                        error_resp = _error_response(None, -32600, "Comando inválido")
                        await self._publish(self._topic_response, error_resp.model_dump())
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Mensaje no parseable: %s", e)
            except ConnectionClosed:
                logger.warning(
                    "Conexión a rosbridge perdida, reconectando en %.1fs...",
                    delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)
                try:
                    self._ws = await connect(self._url)
                    await self._advertise_topics()
                    await self._subscribe_commands()
                    logger.info("Reconectado a rosbridge")
                except (OSError, InvalidURI) as e:
                    logger.error("Error reconectando a rosbridge: %s", e)

    async def _publish_status_loop(self, get_status: Callable[[], dict]):
        """Publica estado periódico del robot como JSON-RPC notification."""
        while True:
            try:
                notification = create_status_notification(get_status())
                await self._publish(self._topic_status, notification.model_dump(mode="json"))
            except ConnectionClosed:
                # El listener se encarga de reconectar, esperamos
                logger.warning("No se pudo publicar status (conexión perdida)")
            except Exception as e:
                logger.error("Error publicando status: %s", e)
            await asyncio.sleep(_STATUS_INTERVAL_SEC)

    async def _publish(self, topic: str, payload: dict):
        """Publica un mensaje en un topic ya advertised."""
        msg = {
            "op": "publish",
            "topic": topic,
            "msg": {"data": json.dumps(payload)},
        }
        await self._ws.send(json.dumps(msg))

    async def _advertise_topics(self):
        """Declara los topics de salida (response y status) en rosbridge.

        Espera brevemente para que rosbridge procese los advertise
        antes de que se empiece a publicar.
        """
        for topic in (self._topic_response, self._topic_status):
            msg = {
                "op": "advertise",
                "topic": topic,
                "type": "std_msgs/String",
            }
            await self._ws.send(json.dumps(msg))
        # Dar tiempo a rosbridge para registrar los publishers internos
        await asyncio.sleep(0.5)
        logger.info("Topics advertised: %s, %s", self._topic_response, self._topic_status)

    async def _subscribe_commands(self):
        """Envía la operación subscribe al topic de comandos."""
        msg = {
            "op": "subscribe",
            "topic": self._topic_command,
            "type": "std_msgs/String",
        }
        await self._ws.send(json.dumps(msg))
        logger.info("Suscrito a %s", self._topic_command)
