"""Interfaz base para strategies de comunicación.

Un strategy representa un canal de comunicación (local o remoto).
Cada strategy traduce entre su protocolo externo y el formato interno
que el micro core entiende y enruta.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, override

from ..json_rpc import JsonRpcCommand, dispatch, to_jsonrpc
from ..robot.responses import RobotResponse, StatusRobotResponse

class State(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"



class Strategy(ABC):
    """Interfaz base que todo strategy debe implementar."""

    _state: State = State.STOPPED

    @property
    def name(self) -> str:
        """Nombre legible del strategy."""
        return type(self).__name__

    @property
    def status(self) -> State:
        """Estado actual del strategy."""
        return self._state

    @abstractmethod
    async def start(self) -> None:
        """Inicializa y conecta el strategy. stopped → running."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Detiene y limpia recursos del strategy. running/paused → stopped."""
        ...

    async def pause(self) -> None:
        """Pausa el strategy. running → paused."""
        self._state = State.PAUSED

    async def resume(self) -> None:
        """Reanuda el strategy. paused → running."""
        self._state = State.RUNNING

    @abstractmethod
    async def receive(self) -> Any:
        """Recibe un mensaje en formato interno. Bloquea hasta tener uno."""
        ...

    @abstractmethod
    async def send(self, message: Any) -> None:
        """Envía un mensaje (formato interno) por el canal."""
        ...

    def get_status_data(self) -> dict[str, Any]:
        return {
            "status": self.status,
        }


class LocalStrategy(Strategy, ABC):

    @abstractmethod
    def get_telemetry_enabled(self) -> bool:
        ...

    @abstractmethod
    def set_telemetry(self, enabled: bool) -> None:
        """Habilita/deshabilita el loop de telemetría periódica."""
        ...

    @override
    def get_status_data(self) -> dict[str, Any]:
        return super().get_status_data() | {
            "telemetry": self.get_telemetry_enabled(),
        }


logger = logging.getLogger(__name__)

STATUS_INTERVAL_SEC = 5.0


class OutboxLocalStrategy(LocalStrategy, ABC):
    """Base de las strategies locales: una cola, tres productores, un consumidor.

    Productores: `send()` (resultado del despacho, con id), `_response_loop`
    (output del robot) y `_telemetry_loop` (snapshot periódico). Consumidor:
    `receive()`, único lugar donde se traduce a JSON-RPC.

    Las subclases construyen `self._robot` en su `__init__` y manejan `start`/`stop`,
    que es donde genuinamente difieren (el mock conecta sync; serial y ROS 2 van a
    executor).
    """

    _robot: Any

    def __init__(self) -> None:
        self._outbox: asyncio.Queue[RobotResponse] = asyncio.Queue()
        self._telemetry_enabled: bool = True
        self._telemetry_task: asyncio.Task[None] | None = None
        self._response_task: asyncio.Task[None] | None = None

    # --- interfaz Strategy ---

    @override
    async def send(self, message: Any) -> None:
        """Despacha el comando. La respuesta correlacionada entra a la misma cola."""
        command = JsonRpcCommand.model_validate(message)
        await self._outbox.put(await dispatch(command, self._robot))

    @override
    async def receive(self) -> Any:
        """Único punto de traducción a JSON-RPC."""
        resp = await self._outbox.get()
        return to_jsonrpc(resp).model_dump(mode="json")

    @override
    def get_telemetry_enabled(self) -> bool:
        return self._telemetry_enabled

    @override
    def set_telemetry(self, enabled: bool) -> None:
        self._telemetry_enabled = enabled
        if enabled and (self._telemetry_task is None or self._telemetry_task.done()):
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        elif not enabled and self._telemetry_task and not self._telemetry_task.done():
            _ = self._telemetry_task.cancel()
            self._telemetry_task = None
        logger.info(
            "Telemetría %s %s", self.name, "habilitada" if enabled else "deshabilitada"
        )

    # --- loops ---

    def _start_loops(self) -> None:
        self._response_task = asyncio.create_task(self._response_loop())
        if self._telemetry_enabled:
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())

    async def _stop_loops(self) -> None:
        """Cancela los loops y ESPERA a que terminen.

        El llamador debe haber llamado `robot.stop_reading()` ANTES:
        `asyncio.to_thread` no se puede cancelar mientras el hilo está bloqueado, así
        que el sentinel es lo que realmente lo desbloquea. Esperar acá es lo que hace
        que `stop()` sea determinista — sin el await, `stop()` retorna con hilos del
        executor todavía vivos.
        """
        for task in (self._response_task, self._telemetry_task):
            if task is None:
                continue
            if not task.done():
                _ = task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._response_task = None
        self._telemetry_task = None

    async def _response_loop(self) -> None:
        """Drena el output del robot de forma continua, haya usuario o no.

        Que este loop sea independiente de `send()` es lo que impide que la lista de
        respuestas del controlador crezca sin tope y que una ráfaga acumulada salga
        de golpe pegada a un comando no relacionado.
        """
        try:
            while True:
                resp = await asyncio.to_thread(self._robot.read_response)
                if resp is None:  # sentinel de parada
                    return
                await self._outbox.put(resp)
        except asyncio.CancelledError:
            pass
        except (ConnectionError, OSError) as e:
            logger.error("Loop de respuestas detenido por error de E/S: %s", e)

    async def _telemetry_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(STATUS_INTERVAL_SEC)
                await self._outbox.put(StatusRobotResponse(self._robot.get_status()))
        except asyncio.CancelledError:
            pass
