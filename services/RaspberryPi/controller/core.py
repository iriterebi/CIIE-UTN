"""Micro core: enrutador puro entre strategies.

No transforma datos — solo mueve mensajes en formato interno
entre el strategy local y el strategy remoto.
Expone un Unix socket para gestión externa (CLI).
"""

import asyncio
import logging
from typing import Any

from .strategy.base import Strategy, LocalStrategy
from .strategy.registry import StrategyRegistry
from .socket_server import SocketServer

logger = logging.getLogger(__name__)


class MicroCore:

    def __init__(self, *, local: LocalStrategy, remote: Strategy, registry: StrategyRegistry, socket_path: str = "/tmp/robot-controller.sock"):
        self.local: LocalStrategy = local
        self.remote: Strategy = remote
        self.registry: StrategyRegistry = registry
        self._running: bool = False

        self._socket: SocketServer = (SocketServer(socket_path)
            .register_method("status", self._handle_status)
            .register_method("switch", self._handle_switch)
            .register_method("connection::local::status", self._handle_connection_local_status)
            .register_method("connection::local::start", self._handle_connection_local_start)
            .register_method("connection::local::stop", self._handle_connection_local_stop)
            .register_method("connection::local::pause", self._handle_connection_local_pause)
            .register_method("connection::local::resume", self._handle_connection_local_resume)
            .register_method("connection::remote::status", self._handle_connection_remote_status)
            .register_method("connection::remote::start", self._handle_connection_remote_start)
            .register_method("connection::remote::stop", self._handle_connection_remote_stop)
            .register_method("connection::remote::pause", self._handle_connection_remote_pause)
            .register_method("connection::remote::resume", self._handle_connection_remote_resume)
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

    # --- connection::local handlers ---

    def _handle_connection_local_status(self) -> dict[str, Any]:
        """Muestra el estado del strategy local."""
        return {"name": self.local.name, "status": self.local.status}

    async def _handle_connection_local_start(self) -> dict[str, Any]:
        """Arranca el strategy local."""
        if self.local._state == "running":
            raise RuntimeError("Strategy local ya está corriendo")
        if self.local._state == "paused":
            await self.local.resume()
        else:
            await self.local.start()
        return {"name": self.local.name, "status": self.local.status}

    async def _handle_connection_local_stop(self) -> dict[str, Any]:
        """Detiene el strategy local."""
        if self.local._state == "stopped":
            raise RuntimeError("Strategy local ya está detenido")
        await self.local.stop()
        return {"name": self.local.name, "status": self.local.status}

    async def _handle_connection_local_pause(self) -> dict[str, Any]:
        """Pausa el strategy local."""
        if self.local._state != "running":
            raise RuntimeError(f"Strategy local no puede pausarse (estado: {self.local._state})")
        await self.local.pause()
        return {"name": self.local.name, "status": self.local.status}

    async def _handle_connection_local_resume(self) -> dict[str, Any]:
        """Reanuda el strategy local."""
        if self.local._state != "paused":
            raise RuntimeError(f"Strategy local no puede reanudarse (estado: {self.local._state})")
        await self.local.resume()
        return {"name": self.local.name, "status": self.local.status}

    # --- connection::remote handlers ---

    def _handle_connection_remote_status(self) -> dict[str, Any]:
        """Muestra el estado del strategy remoto."""
        return {"name": self.remote.name, "status": self.remote.status}

    async def _handle_connection_remote_start(self) -> dict[str, Any]:
        """Arranca el strategy remoto."""
        if self.remote._state == "running":
            raise RuntimeError("Strategy remoto ya está corriendo")
        if self.remote._state == "paused":
            await self.remote.resume()
        else:
            await self.remote.start()
        return {"name": self.remote.name, "status": self.remote.status}

    async def _handle_connection_remote_stop(self) -> dict[str, Any]:
        """Detiene el strategy remoto."""
        if self.remote._state == "stopped":
            raise RuntimeError("Strategy remoto ya está detenido")
        await self.remote.stop()
        return {"name": self.remote.name, "status": self.remote.status}

    async def _handle_connection_remote_pause(self) -> dict[str, Any]:
        """Pausa el strategy remoto."""
        if self.remote._state != "running":
            raise RuntimeError(f"Strategy remoto no puede pausarse (estado: {self.remote._state})")
        await self.remote.pause()
        return {"name": self.remote.name, "status": self.remote.status}

    async def _handle_connection_remote_resume(self) -> dict[str, Any]:
        """Reanuda el strategy remoto."""
        if self.remote._state != "paused":
            raise RuntimeError(f"Strategy remoto no puede reanudarse (estado: {self.remote._state})")
        await self.remote.resume()
        return {"name": self.remote.name, "status": self.remote.status}

    # --- routing ---

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
