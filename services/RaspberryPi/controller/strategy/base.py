"""Interfaz base para strategies de comunicación.

Un strategy representa un canal de comunicación (local o remoto).
Cada strategy traduce entre su protocolo externo y el formato interno
que el micro core entiende y enruta.
"""

from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any, override

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
