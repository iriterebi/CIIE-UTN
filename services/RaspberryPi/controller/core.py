"""Micro core: enrutador puro entre strategies.

No transforma datos — solo mueve mensajes en formato interno
entre el strategy local y el strategy remoto.
Expone un Unix socket para gestión externa (CLI).
"""

import asyncio
import logging
from enum import StrEnum
from functools import partial
from typing import TypedDict

from .strategy.base import Strategy, LocalStrategy, State as StrategyState
from .strategy.registry import StrategyRegistry
from .socket_server import SocketServer
from .type_defs import StatusData, CoreStatusData

logger = logging.getLogger(__name__)


class Side(StrEnum):
    LOCAL = "local"
    REMOTE = "remote"

class Strategies(TypedDict):
    local: LocalStrategy
    remote: Strategy


class MicroCore:

    def __init__(self, *, local: LocalStrategy, remote: Strategy, registry: StrategyRegistry, socket_path: str = "/tmp/robot-controller.sock"):
        self.local: LocalStrategy = local
        self.remote: Strategy = remote
        self.registry: StrategyRegistry = registry
        self._running: bool = False

        self._socket: SocketServer = (SocketServer(socket_path)
            .register_method("status", self._handle_status)
            .register_method("switch", self._handle_switch)
        )

        for side in Side:
            for action, handler in [
                ("status", self._handle_connection_status),
                ("start", self._handle_connection_start),
                ("stop", self._handle_connection_stop),
                ("pause", self._handle_connection_pause),
                ("resume", self._handle_connection_resume),
            ]:
                self._socket.register_method(  # pyright: ignore[reportUnusedCallResult]
                    f"connection::{side}::{action}",
                    partial(handler, side),
                )

    def _get_strategy(self, side: Side) -> Strategy:
        match side:
            case Side.LOCAL:
                return self.local
            case Side.REMOTE:
                return self.remote
            case _:
                raise ValueError(f"Side desconocido: {side}")  # pyright: ignore[reportUnreachable]

    # --- lifecycle ---

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

    # --- global handlers ---

    def _handle_status(self) -> CoreStatusData:
        """Muestra el estado del core y los strategies."""

        return CoreStatusData(
            core = "running" if self._running else "starting",
            local = self._handle_connection_status(Side.LOCAL),
            remote = self._handle_connection_status(Side.REMOTE),
        )

    def _handle_switch(self, enabled: bool) -> StatusData:
        """Habilita/deshabilita la telemetría del strategy local."""
        self.local.set_telemetry(enabled)
        return self._get_strategy_staus(self.local)

    # --- connection handlers (parametrizados por side) ---

    def _handle_connection_status(self, side: Side) -> StatusData:
        """Muestra el estado de un strategy."""
        return self._get_strategy_staus(self._get_strategy(side))

    def _get_strategy_staus(self, s: Strategy) -> StatusData:
        return s.get_status_data() | {"name": s.name}

    async def _handle_connection_start(self, side: Side) -> StatusData:
        """Arranca un strategy."""
        s = self._get_strategy(side)

        match s.status:
            case StrategyState.RUNNING:
                raise RuntimeError(f"Strategy {side} ya está corriendo")
            case StrategyState.PAUSED:
                await s.resume()
            case _:
                await s.start()

        return self._get_strategy_staus(s)

    async def _handle_connection_stop(self, side: Side) -> StatusData:
        """Detiene un strategy."""
        s = self._get_strategy(side)
        if s.status == StrategyState.STOPPED:
            raise RuntimeError(f"Strategy {side} ya está detenido")
        await s.stop()
        return self._get_strategy_staus(s)

    async def _handle_connection_pause(self, side: Side) -> StatusData:
        """Pausa un strategy."""
        s = self._get_strategy(side)
        if s.status != StrategyState.RUNNING:
            raise RuntimeError(f"Strategy {side} no puede pausarse (estado: {s.status})")
        await s.pause()
        return self._get_strategy_staus(s)

    async def _handle_connection_resume(self, side: Side) -> StatusData:
        """Reanuda un strategy."""
        s = self._get_strategy(side)
        if s.status != StrategyState.PAUSED:
            raise RuntimeError(f"Strategy {side} no puede reanudarse (estado: {s.status})")
        await s.resume()
        return self._get_strategy_staus(s)

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
