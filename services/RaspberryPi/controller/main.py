#!/usr/bin/env python3

"""Punto de entrada del controlador de robot.

Crea los strategies (local + remoto), los inyecta en el micro core y arranca.
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
from .strategy.local.mock_strategy import MockStrategy
from .strategy.local.serial_strategy import SerialStrategy
from .strategy.remote.rosbridge_strategy import RosbridgeStrategy


async def async_main():
    local = (
        MockStrategy(config.arduino_port)
        if config.mock_robot
        else SerialStrategy(config.arduino_port)
    )

    remote = RosbridgeStrategy(
        server_url=config.server_url,
        rosbridge_url=config.rosbridge_url,
        metadata_file=config.metadata_file,
        create_default_metadata=config.create_default_metadata,
    )

    core = MicroCore(local=local, remote=remote, socket_path=config.socket_path)
    await core.run()


def main():
    asyncio.run(async_main())
