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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Controlador de robot — se registra en la API y escucha comandos vía rosbridge."
    )
    parser.add_argument(
        '--metadata-file',
        default=config.metadata_file,
        help="Ruta al archivo de credenciales del robot (default: env METADATA_FILE o ./robot-metadata.json)",
    )
    return parser.parse_args()


async def async_main(credentials: RobotCredentials, robot):
    logging.info("Iniciando comunicación con rosbridge vía WebSocket. %s", config.rosbridge_url)
    """Fase operativa: comunicación con rosbridge vía WebSocket."""
    async with PiRosBridgeClient(config.rosbridge_url, credentials) as client:
        await client.run(
            on_command=lambda cmd: handle_json_rpc(cmd, robot),
            get_status=robot.get_status,
        )


def main():
    args = parse_args()

    with (
        ServerServices(
            base_url=config.server_url,
            metadata_file=args.metadata_file,
            create_default_config=config.create_default_metadata,
        ) as service,
        RobotController(config.arduino_port) as robot,
    ):
        asyncio.run(async_main(service.credentials, robot))
