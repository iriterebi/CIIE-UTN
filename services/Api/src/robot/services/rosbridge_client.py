"""Cliente WebSocket para comunicación con rosbridge_suite.

Mantiene una conexión persistente a rosbridge (ws://rosbridge:9090),
publica comandos a topics ROS y rutea respuestas a las queues de los usuarios.
"""

import asyncio
import json
import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed

from ..utils.crockford_base32 import uuid_to_crockford_base32
from ..entities import Robot


logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


class RosBridgeClient:
    """Cliente singleton que se comunica con rosbridge_suite via WebSocket."""

    def __init__(self, url: str):
        self._url = url
        self._ws: ClientConnection | None = None
        self._subscribed_robots: set[str] = set()
        self._advertised_robots: set[str] = set()
        self._response_queues: dict[str, set[asyncio.Queue]] = {}
        self._listener_task: asyncio.Task | None = None

    async def connect(self):
        """Conectar al rosbridge WebSocket y arrancar el listener."""
        self._ws = await connect(self._url)
        self._listener_task = asyncio.create_task(self._listen())
        logger.info("Conectado a rosbridge en %s", self._url)

    async def disconnect(self):
        """Cerrar conexión y cancelar listener."""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
        logger.info("Desconectado de rosbridge")

    async def _listen(self):
        """Loop principal: recibe mensajes de rosbridge y los rutea a las queues."""
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                async for raw in self._ws:
                    delay = _MIN_RECONNECT_DELAY
                    try:
                        msg = json.loads(raw)
                        self._route_message(msg)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning("Mensaje de rosbridge no parseado: %s", e)
            except ConnectionClosed:
                logger.warning(
                    "Conexión a rosbridge perdida, reconectando en %.1fs...", delay
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)
                try:
                    self._ws = await connect(self._url)
                    await self._readvertise_and_resubscribe_all()
                    logger.info("Reconectado a rosbridge")
                except Exception as e:
                    logger.error("Error reconectando a rosbridge: %s", e)

    def _route_message(self, msg: dict):
        """Parsea el topic del mensaje y lo envía a las queues correspondientes."""
        topic = msg.get("topic", "")
        data_str = msg.get("msg", {}).get("data", "{}")

        # Topic format: /robot/r<base32>/response o /robot/r<base32>/status
        parts = topic.split("/")
        if len(parts) != 4 or parts[1] != "robot":
            return

        raw_segment = parts[2]  # "r<base32>"
        if not raw_segment.startswith("r"):
            return
        base32_id = raw_segment[1:]  # quitar prefijo "r"
        # suffix = parts[3]  # "response" o "status"

        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            payload = {"raw": data_str}

        # Buscar queues por base32_id
        queues = self._response_queues.get(base32_id, set())
        for queue in queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("Queue llena, descartando mensaje para %s", base32_id)

    async def publish_command(self, robor: Robot, command_payload: dict):
        """Publicar comando al topic /robot/<base32>/command."""
        b32 = uuid_to_crockford_base32(robor.id)
        await self._ensure_advertised(b32)
        msg = {
            "op": "publish",
            "topic": f"/robot/r{b32}/command",
            "msg": {"data": json.dumps(command_payload)}
        }
        await self._ws.send(json.dumps(msg))

    async def subscribe_robot(self, robot: Robot, queue: asyncio.Queue):
        """Registrar una queue para recibir respuestas/status de un robot."""
        b32 = uuid_to_crockford_base32(robot.id)
        await self._ensure_subscribed(b32)
        self._response_queues.setdefault(b32, set()).add(queue)

    async def unsubscribe_robot(self, robot: Robot, queue: asyncio.Queue):
        """Desregistrar una queue de un robot."""
        b32 = uuid_to_crockford_base32(robot.id)
        if b32 in self._response_queues:
            self._response_queues[b32].discard(queue)

    async def _ensure_advertised(self, b32: str):
        """Advertise del topic command de un robot si aún no lo hicimos."""
        if b32 in self._advertised_robots:
            return
        msg = {
            "op": "advertise",
            "topic": f"/robot/r{b32}/command",
            "type": "std_msgs/String",
        }
        await self._ws.send(json.dumps(msg))
        self._advertised_robots.add(b32)
        logger.info("Advertised topic /robot/%s/command", b32)

    async def _ensure_subscribed(self, b32: str):
        """Suscribirse a los topics de un robot en rosbridge si aún no lo estamos."""
        if b32 in self._subscribed_robots:
            return
        for suffix in ("response", "status"):
            msg = {
                "op": "subscribe",
                "topic": f"/robot/r{b32}/{suffix}",
                "type": "std_msgs/String"
            }
            await self._ws.send(json.dumps(msg))
        self._subscribed_robots.add(b32)
        logger.info("Suscrito a topics de robot %s", b32)

    async def _readvertise_and_resubscribe_all(self):
        """Re-advertise y re-suscribirse a todos los robots tras una reconexión."""
        advertised = list(self._advertised_robots)
        self._advertised_robots.clear()
        for b32 in advertised:
            await self._ensure_advertised(b32)

        subscribed = list(self._subscribed_robots)
        self._subscribed_robots.clear()
        for b32 in subscribed:
            await self._ensure_subscribed(b32)


# --- Dependency Injection ---

_rosbridge_client: RosBridgeClient | None = None


def set_rosbridge_client(client: RosBridgeClient):
    global _rosbridge_client
    _rosbridge_client = client


def get_rosbridge_client() -> RosBridgeClient:
    if _rosbridge_client is None:
        raise RuntimeError("RosBridge client no inicializado")
    return _rosbridge_client


RosBridgeClientDep = Annotated[RosBridgeClient, Depends(get_rosbridge_client)]
