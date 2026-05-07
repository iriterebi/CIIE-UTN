#!/usr/bin/env python3

"""Punto de entrada del controlador de robot.

Construye el registro de strategies, selecciona por config, inyecta en el core y arranca.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

from .config import config
from .core import MicroCore
from .strategy.base import Strategy, LocalStrategy
from .strategy.registry import StrategyRegistry
from .strategy.local.mock_strategy import MockStrategy
from .strategy.local.serial_strategy import SerialStrategy
from .strategy.remote.rosbridge_strategy import RosbridgeStrategy
from .strategy.remote.ws_strategy import WsStrategy


registry = StrategyRegistry(
    remote=[RosbridgeStrategy, WsStrategy],
    local=[MockStrategy, SerialStrategy],
)


def create_local(name: str) -> LocalStrategy:
    """Factory: instancia un strategy local por nombre."""
    match name:
        case "MockStrategy":
            return MockStrategy(config.arduino_port)
        case "SerialStrategy":
            return SerialStrategy(config.arduino_port)
        case _:
            available = ", ".join(registry.list_local())
            raise ValueError(f"Strategy local desconocido: '{name}'. Disponibles: {available}")


def create_remote(name: str) -> Strategy:
    """Factory: instancia un strategy remoto por nombre."""
    match name:
        case "RosbridgeStrategy":
            return RosbridgeStrategy(
                server_url=config.server_url,
                rosbridge_url=config.rosbridge_url,
                metadata_file=config.metadata_file,
                create_default_metadata=config.create_default_metadata,
            )
        case "WsStrategy":
            return WsStrategy(
                server_url=config.server_url,
                metadata_file=config.metadata_file,
                create_default_metadata=config.create_default_metadata,
            )
        case _:
            available = ", ".join(registry.list_remote())
            raise ValueError(f"Strategy remoto desconocido: '{name}'. Disponibles: {available}")


async def async_main():
    local = create_local(config.local_strategy)
    remote = create_remote(config.remote_strategy)

    core = MicroCore(
        local=local,
        remote=remote,
        registry=registry,
        socket_path=config.socket_path,
    )
    await core.run()


def main():
    asyncio.run(async_main())
