"""Micro core: enrutador puro entre strategies.

No transforma datos — solo mueve mensajes en formato interno
entre el strategy local y el strategy remoto.
Expone un Unix socket para gestión externa (CLI).
"""

import asyncio
import logging
from typing import Any

from .strategy.base import Strategy, LocalStrategy
from .socket_server import SocketServer

logger = logging.getLogger(__name__)


class MicroCore:

    def __init__(self, *, local: LocalStrategy, remote: Strategy, socket_path: str = "/tmp/robot-controller.sock"):
        self.local: LocalStrategy = local
        self.remote: Strategy = remote
        self._running: bool = False

        self._socket: SocketServer = (SocketServer(socket_path)
            .register_method("status", self._handle_status)
            .register_method("switch", self._handle_switch)
        )

    async def run(self) -> None:
        """Arranca socket server, strategies, y enruta mensajes.

        El socket arranca primero para que el CLI pueda consultar
        estado incluso durante el arranque de los strategies.
        """
        await self._socket.start()

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._socket.serve_forever())  # pyright: ignore[reportUnusedCallResult]
                tg.create_task(self._start_and_route())  # pyright: ignore[reportUnusedCallResult]
        finally:
            await self.stop()

    async def _start_and_route(self) -> None:
        """Arranca strategies y luego enruta mensajes."""
        await self.remote.start()
        await self.local.start()
        self._running = True
        logger.info("Micro core iniciado — enrutando mensajes")

        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._route_remote_to_local())  # pyright: ignore[reportUnusedCallResult]
            tg.create_task(self._route_local_to_remote())  # pyright: ignore[reportUnusedCallResult]

    async def stop(self):
            await self._socket.stop()
            await self.local.stop()
            await self.remote.stop()
            logger.info("Micro core detenido")

    def _handle_status(self) -> dict[str, Any]:
        """Muestra el estado del core y los strategies."""
        return {
            "core": "running" if self._running else "starting",
            "local": {
                "name": self.local.name,
                "status": self.local.status,
            },
            "remote": {
                "name": self.remote.name,
                "status": self.remote.status,
            },
        }

    def _handle_switch(self, enabled: bool) -> dict[str, Any]:
        """Habilita/deshabilita la telemetría del strategy local."""
        self.local.set_telemetry(enabled)
        return {"telemetry": enabled}

    async def _route_remote_to_local(self) -> None:
        """Remoto → Local: comandos de la API/rosbridge al robot."""
        while True:
            message = await self.remote.receive()
            await self.local.send(message)

    async def _route_local_to_remote(self) -> None:
        """Local → Remoto: respuestas/status del robot a la API/rosbridge."""
        while True:
            message = await self.local.receive()
            await self.remote.send(message)
