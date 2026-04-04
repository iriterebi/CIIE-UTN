"""Interfaz base para strategies de comunicación.

Un strategy representa un canal de comunicación (local o remoto).
Cada strategy traduce entre su protocolo externo y el formato interno
que el micro core entiende y enruta.
"""

from abc import ABC, abstractmethod
from typing import Any


class Strategy(ABC):
    """Interfaz base que todo strategy debe implementar."""

    _state: str = "stopped"

    @property
    def name(self) -> str:
        """Nombre legible del strategy."""
        return type(self).__name__

    @property
    def status(self) -> str:
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
        self._state = "paused"

    async def resume(self) -> None:
        """Reanuda el strategy. paused → running."""
        self._state = "running"

    @abstractmethod
    async def receive(self) -> Any:
        """Recibe un mensaje en formato interno. Bloquea hasta tener uno."""
        ...

    @abstractmethod
    async def send(self, message: Any) -> None:
        """Envía un mensaje (formato interno) por el canal."""
        ...


class LocalStrategy(Strategy, ABC):
    @abstractmethod
    def set_telemetry(self, enabled: bool) -> None:
        """Habilita/deshabilita el loop de telemetría periódica."""
        ...
