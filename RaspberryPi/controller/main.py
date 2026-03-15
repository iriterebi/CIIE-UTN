#!/usr/bin/env python3

"""Punto de entrada del controlador de robot.

Flujo:
1. (sync) Carga config, registra el robot en la API, handshake con retry
2. (async) Conecta a rosbridge, escucha comandos y publica estado
"""

import asyncio
import logging
import sys

from .config import ARDUINO_PORT, CREATE_DEFAULT_METADATA, ROSBRIDGE_URL
from .server.server_service import ServerServices
from .robot import RobotController
from .rosbridge import PiRosBridgeClient
from .rosbridge.json_rpc import handle_json_rpc
from .server.server_service import RobotCredentials



async def async_main(credentials: RobotCredentials, robot):
    """Fase operativa: comunicación con rosbridge vía WebSocket."""
    async with PiRosBridgeClient(ROSBRIDGE_URL, credentials) as client:
        await client.run(
            on_command=lambda cmd: handle_json_rpc(cmd, robot),
            get_status=robot.get_status,
        )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )

    service = ServerServices()

    if not service.load_external_config() and CREATE_DEFAULT_METADATA:
        service.create_default_config()

    with service, RobotController(ARDUINO_PORT) as robot:
        asyncio.run(async_main(service.credentials, robot))
