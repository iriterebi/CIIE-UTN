"""Interfaz base para strategies de comunicación.

Un strategy representa un canal de comunicación (local o remoto).
Cada strategy traduce entre su protocolo externo y el formato interno
que el micro core entiende y enruta.
"""

from abc import ABC, abstractmethod
from typing import Any


class Strategy(ABC):
    """Interfaz base que todo strategy debe implementar."""

    @abstractmethod
    async def start(self) -> None:
        """Inicializa y conecta el strategy."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Detiene y limpia recursos del strategy."""
        ...

    @abstractmethod
    async def receive(self) -> Any:
        """Recibe un mensaje en formato interno. Bloquea hasta tener uno."""
        ...

    @abstractmethod
    async def send(self, message: Any) -> None:
        """Envía un mensaje (formato interno) por el canal."""
        ...
