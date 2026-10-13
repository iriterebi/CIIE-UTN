"""Punto de entrada del controlador de robot.

Construye el registro de strategies, selecciona por config, inyecta en el core y arranca.
Corre en paralelo el pipeline de video de la cámara (CameraRelay + VideoWsClient),
independiente del LOCAL_STRATEGY del brazo — ver
docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
"""

import asyncio
import logging
import signal
import sys
from contextlib import ExitStack
from typing import TYPE_CHECKING

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
)

from .config import Config, config
from .core import MicroCore
from .server.server_service import ServerServices
from .strategy.base import LocalStrategy, Strategy
from .strategy.registry import StrategyRegistry
from .strategy.remote.ws_strategy import WsStrategy

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from rclpy.executors import Executor


# try:
#     import rclpy  # import diferido: requiere entorno ROS 2 sourceado
#     from rclpy.node import Node
#     from std_msgs.msg import String
# except ImportError as e:

def create_local(name: str, registry: StrategyRegistry, rclExecutor: Executor | None) -> LocalStrategy:
    """Factory: instancia un strategy local por nombre."""
    match name:
        case "MockStrategy" if registry.has_local("MockStrategy"):
            from .strategy.local.mock_strategy import MockStrategy
            return MockStrategy(config.arduino_port)

        case "Ros2Strategy" if registry.has_local("Ros2Strategy"):
            from .strategy.local.ros2_strategy import Ros2Strategy
            assert rclExecutor is not None

            return Ros2Strategy(
                node_name=config.ros2_node_name,
                command_topic=config.ros2_command_topic,
                data_topic=config.ros2_data_topic,
                rclExecutor=rclExecutor
            )

        case _:
            available = ", ".join(registry.list_local())
            raise ValueError(f"Strategy local desconocido: '{name}'. Disponibles: {available}")


def create_remote(name: str, registry: StrategyRegistry) -> Strategy:
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


async def run_camera_pipeline(cfg: Config, rclExecutor: Executor) -> None:
    """Sube CameraRelay + VideoWsClient. Cualquier error queda contenido acá (se
    loguea y el video se deshabilita): no debe tumbar el resto del controller.

    `VideoWsClient.run` no retorna (reintenta por su cuenta ante cortes); sólo
    termina por cancelación, y el `finally` libera el nodo de la cámara.
    """
    try:
        from .camera import CameraRelay, VideoWsClient
        from .camera.video_ws_client import derive_video_ws_url

        relay = CameraRelay(
            node_name=cfg.camera_node_name,
            camera_topic=cfg.camera_topic,
            jpeg_quality=cfg.camera_jpeg_quality,
            rclExecutor=rclExecutor
        )

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, relay.connect, loop)

        server_service = ServerServices(
            base_url=cfg.server_url,
            metadata_file=cfg.metadata_file,
            create_default_config=cfg.create_default_metadata,
        )
        client = VideoWsClient(
            server_service=server_service,
            ws_url=derive_video_ws_url(cfg.server_url),
        )
        try:
            await client.run(relay.next_frame)
        finally:
            await loop.run_in_executor(None, relay.disconnect)
    except Exception:
        logger.exception("Pipeline de video terminó por un error inesperado (no afecta al resto del controller)")


async def spin_executor(executor: Executor) -> None:
    """Corre `executor.spin()` en un thread para no bloquear el event loop.

    `to_thread` no se puede cancelar: al cancelar esta tarea, `executor.shutdown()`
    es lo que despierta al thread y corta el spin.
    """
    try:
        await asyncio.to_thread(executor.spin)
    finally:
        _ = executor.shutdown()


async def async_main():
    # SIGTERM (docker stop) no lo maneja asyncio.run: sin este handler, como PID 1
    # la señal se ignora y el contenedor muere por SIGKILL sin limpiar.
    main_task = asyncio.current_task()
    assert main_task is not None
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, main_task.cancel)

    with ExitStack() as stack:

        from .strategy.local.mock_strategy import MockStrategy

        registry = StrategyRegistry(
            remote=[WsStrategy],
            local=[MockStrategy],
        )


        executor: Executor | None = None

        try:
            import rclpy
            from rclpy.executors import MultiThreadedExecutor
            from rclpy.signals import SignalHandlerOptions

            from .strategy.local.ros2_strategy import Ros2Strategy

            registry.add_local(Ros2Strategy)

            # Sin handlers de rclpy: si no, SIGINT/SIGTERM matan el contexto antes
            # del apagado ordenado de la app. Las señales las maneja asyncio.
            rclpyCtx = rclpy.init(
                domain_id=config.ros2_domain_id,
                signal_handler_options=SignalHandlerOptions.NO,
            )
            _ = stack.push(rclpyCtx)

            executor = MultiThreadedExecutor()
            _ = stack.push(executor)


        except ImportError:
            _ = logger.exception("rclpy couldn't be enabled")

        local = create_local(config.local_strategy, registry, executor)
        remote = create_remote(config.remote_strategy, registry)


        core = MicroCore(
            local=local,
            remote=remote,
            registry=registry,
            socket_path=config.socket_path,
        )

        if executor is not None:
            async with asyncio.TaskGroup() as tg:
                _ = tg.create_task(core.run())
                _ = tg.create_task(run_camera_pipeline(config, executor))
                _ = tg.create_task(spin_executor(executor))
        else:
            await core.run()


def main():
    try:
        asyncio.run(async_main())
    except asyncio.CancelledError:
        logger.info("Controller detenido por SIGTERM")
