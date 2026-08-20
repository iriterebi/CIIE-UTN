#!/usr/bin/env python3

"""Punto de entrada del controlador de robot.

Construye el registro de strategies, selecciona por config, inyecta en el core y arranca.
Corre en paralelo el pipeline de video de la cámara (CameraRelay + VideoWsClient),
independiente del LOCAL_STRATEGY del brazo — ver
docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

from .camera import CameraRelay, VideoWsClient
from .camera.video_ws_client import _derive_video_ws_url
from .config import Config, config
from .core import MicroCore
from .server.server_service import ServerServices
from .strategy.base import Strategy, LocalStrategy
from .strategy.registry import StrategyRegistry
from .strategy.local.mock_strategy import MockStrategy
from .strategy.local.serial_strategy import SerialStrategy
from .strategy.local.ros2_strategy import Ros2Strategy
from .strategy.remote.ws_strategy import WsStrategy

logger = logging.getLogger(__name__)


registry = StrategyRegistry(
    remote=[WsStrategy],
    local=[MockStrategy, SerialStrategy, Ros2Strategy],
)


def create_local(name: str) -> LocalStrategy:
    """Factory: instancia un strategy local por nombre."""
    match name:
        case "MockStrategy":
            return MockStrategy(config.arduino_port)
        case "SerialStrategy":
            return SerialStrategy(config.arduino_port)
        case "Ros2Strategy":
            return Ros2Strategy(
                node_name=config.ros2_node_name,
                command_topic=config.ros2_command_topic,
                data_topic=config.ros2_data_topic,
                domain_id=config.ros2_domain_id,
            )
        case _:
            available = ", ".join(registry.list_local())
            raise ValueError(f"Strategy local desconocido: '{name}'. Disponibles: {available}")


def create_remote(name: str) -> Strategy:
    """Factory: instancia un strategy remoto por nombre."""
    match name:
        case "WsStrategy":
            return WsStrategy(
                server_url=config.server_url,
                metadata_file=config.metadata_file,
                create_default_metadata=config.create_default_metadata,
            )
        case _:
            available = ", ".join(registry.list_remote())
            raise ValueError(f"Strategy remoto desconocido: '{name}'. Disponibles: {available}")


async def run_camera_pipeline(cfg: Config) -> None:
    """Sube CameraRelay + VideoWsClient. No-op silencioso si falta rclpy/cv2 —
    no debe tumbar el resto del controller (mismo patrón que Ros2Controller)."""
    relay = CameraRelay(
        node_name=cfg.camera_node_name,
        camera_topic=cfg.camera_topic,
        jpeg_quality=cfg.camera_jpeg_quality,
        domain_id=cfg.ros2_domain_id,
    )

    loop = asyncio.get_running_loop()
    try:
        await loop.run_in_executor(None, relay.connect, loop)
    except EnvironmentError as e:
        logger.warning("Cámara no disponible, video deshabilitado: %s", e)
        return

    server_service = ServerServices(
        base_url=cfg.server_url,
        metadata_file=cfg.metadata_file,
        create_default_config=cfg.create_default_metadata,
    )
    client = VideoWsClient(
        server_service=server_service,
        ws_url=_derive_video_ws_url(cfg.server_url),
    )
    try:
        await client.run(relay.next_frame)
    except EnvironmentError as e:
        logger.warning("No se pudo autenticar VideoWsClient, video deshabilitado: %s", e)
    finally:
        await loop.run_in_executor(None, relay.disconnect)


async def async_main():
    local = create_local(config.local_strategy)
    remote = create_remote(config.remote_strategy)

    core = MicroCore(
        local=local,
        remote=remote,
        registry=registry,
        socket_path=config.socket_path,
    )

    async with asyncio.TaskGroup() as tg:
        tg.create_task(core.run())
        tg.create_task(run_camera_pipeline(config))


def main():
    asyncio.run(async_main())
