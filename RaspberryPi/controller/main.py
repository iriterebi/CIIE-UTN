#!/usr/bin/env python3

"""Punto de entrada del controlador de robot.

Flujo:
1. (sync) Carga config, registra el robot en la API, handshake con retry
2. (async) Conecta a rosbridge, escucha comandos y publica estado
"""

import argparse
import asyncio
import logging
import sys

from .config import ARDUINO_PORT, CREATE_DEFAULT_METADATA, METADATA_FILE, ROSBRIDGE_URL, SERVER_URL

from .server.server_service import ServerServices
from .robot import RobotController
from .rosbridge import PiRosBridgeClient
from .rosbridge.json_rpc import handle_json_rpc
from .server.server_service import RobotCredentials


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlador de robot — se registra en la API y escucha comandos vía rosbridge."
    )
    parser.add_argument(
        '--metadata-file',
        default=METADATA_FILE,
        help="Ruta al archivo de credenciales del robot (default: env METADATA_FILE o ./robot-metadata.json)",
    )
    return parser.parse_args()


async def async_main(credentials: RobotCredentials, robot):
    """Fase operativa: comunicación con rosbridge vía WebSocket."""
    async with PiRosBridgeClient(ROSBRIDGE_URL, credentials) as client:
        await client.run(
            on_command=lambda cmd: handle_json_rpc(cmd, robot),
            get_status=robot.get_status,
        )


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )

    with (
        ServerServices(
            base_url=SERVER_URL,
            metadata_file=args.metadata_file,
            create_default_config=CREATE_DEFAULT_METADATA,
        ) as service,
        RobotController(ARDUINO_PORT) as robot,
    ):
        asyncio.run(async_main(service.credentials, robot))
