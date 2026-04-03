#!/usr/bin/env python3
# pyright: reportUnusedCallResult=false

"""Punto de entrada del controlador de robot.

Flujo:
1. (sync) Carga config, registra el robot en la API, handshake con retry
2. (async) Conecta a rosbridge, escucha comandos y publica estado
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
from .server.server_service import ServerServices
from .robot import RobotController
from .rosbridge import PiRosBridgeClient
from .rosbridge.json_rpc import handle_json_rpc
from .server.server_service import RobotCredentials


async def async_main(credentials: RobotCredentials, robot: RobotController):
    """Fase operativa: comunicación con rosbridge vía WebSocket."""

    logging.info("Iniciando comunicación con rosbridge vía WebSocket. %s", config.rosbridge_url)

    async with PiRosBridgeClient(config.rosbridge_url, credentials) as client:

        await client.run(
            on_command=lambda cmd: handle_json_rpc(cmd, robot),
            get_status=robot.get_status,
        )


def main():
    with (
        ServerServices(
            base_url=config.server_url,
            metadata_file=config.metadata_file,
            create_default_config=config.create_default_metadata,
        ) as service,
        RobotController(config.arduino_port) as robot,
    ):
        asyncio.run(async_main(service.credentials, robot))  # pyright: ignore[reportArgumentType]
