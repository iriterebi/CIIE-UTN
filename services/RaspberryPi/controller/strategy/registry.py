"""Registro de strategies disponibles.

Almacena clases (types), no instancias. Las instancias se crean al seleccionar.
"""

from dataclasses import dataclass, field

from .base import Strategy, LocalStrategy


@dataclass
class StrategyRegistry:
    remote: list[type[Strategy]] = field(default_factory=list)
    local: list[type[LocalStrategy]] = field(default_factory=list)

    def get_remote(self, name: str) -> type[Strategy] | None:
        """Busca un strategy remoto por nombre de clase."""
        for cls in self.remote:
            if cls.__name__ == name:
                return cls
        return None

    def get_local(self, name: str) -> type[LocalStrategy] | None:
        """Busca un strategy local por nombre de clase."""
        for cls in self.local:
            if cls.__name__ == name:
                return cls
        return None

    def list_remote(self) -> list[str]:
        """Retorna nombres de strategies remotos disponibles."""
        return [cls.__name__ for cls in self.remote]

    def list_local(self) -> list[str]:
        """Retorna nombres de strategies locales disponibles."""
        return [cls.__name__ for cls in self.local]
