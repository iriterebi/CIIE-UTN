"""Suscriptor ROS 2 de la cámara: convierte frames de usb_cam/image_raw en JPEG.

IPC interno de la Pi (ver ARQUITECTURA.md, §Rol de ROS 2 en el CLAUDE.md raíz) —
no es un Strategy: es push-only, no habla JSON-RPC, y corre independiente del
LOCAL_STRATEGY activo para el brazo (el robot puede controlarse por serial y
aun así tener cámara vía ROS 2, son preocupaciones separadas). Ver
docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.

`rclpy`/`sensor_msgs`/`cv2`/`numpy` se importan de forma **diferida** dentro de
`connect()`, mismo patrón que `robot/ros2_controller.py`, para que el módulo se
pueda importar (y el modo demo/tests corran) sin tener ROS 2/opencv instalados.
"""

import asyncio
import logging
import os

import cv2
import numpy as np
from rclpy.executors import Executor
from rclpy.node import Node
from sensor_msgs.msg import Image

logger = logging.getLogger(__name__)


class CameraRelay:
    """Último frame gana: la cola tiene capacidad 1, se pisa el anterior si
    nadie lo consumió (ver Global Constraints del plan — sin buffering)."""

    def __init__(
        self,
        *,
        node_name: str,
        camera_topic: str,
        rclExecutor: Executor,
        jpeg_quality: int = 80,
    ):
        self.node_name: str = node_name
        self.camera_topic: str = camera_topic
        self.jpeg_quality: int = jpeg_quality
        self.rclExecutor: Executor = rclExecutor

        self._node: Node | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)

        self.logger = logging.getLogger(__name__)

    def connect(self, loop: asyncio.AbstractEventLoop) -> None:
        """Sync — pensado para correr en `run_in_executor` (mismo patrón que
        `Ros2Controller.connect`). Recibe `loop` explícito porque se llama
        desde un worker thread, donde `asyncio.get_running_loop()` no ve el
        loop del thread principal.
        """

        self._loop = loop

        self._node = Node(self.node_name)
        _ = self._node.create_subscription(Image, self.camera_topic, self._on_frame, 10)
        _ = self.rclExecutor.add_node(self._node)

        self.logger.info(
            "CameraRelay conectado (node=%s, domain=%s, topic=%s)",
            self.node_name,
            os.environ.get("ROS_DOMAIN_ID"),
            self.camera_topic,
        )

    def _on_frame(self, msg: Image) -> None:
        """Callback de ROS 2 (corre en el thread de spin). Codifica bgr8 → JPEG."""
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(  # pyright: ignore[reportAny]
            msg.height, msg.width, 3
        )
        ok, encoded = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            self.logger.warning("No se pudo codificar el frame a JPEG")
            return

        jpeg_bytes = encoded.tobytes()
        assert self._loop is not None
        _ = self._loop.call_soon_threadsafe(self._push, jpeg_bytes)

    def _push(self, jpeg_bytes: bytes) -> None:
        """Corre en el loop asyncio (vía call_soon_threadsafe)."""
        if self._queue.full():
            _ = self._queue.get_nowait()
        self._queue.put_nowait(jpeg_bytes)

    async def next_frame(self) -> bytes:
        return await self._queue.get()

    def disconnect(self) -> None:
        if self._node is not None:
            try:
                _ = self.rclExecutor.remove_node(self._node)
                self._node.destroy_node()
            except Exception:
                self.logger.exception("destroy_node falló: %s")

        self.logger.info("CameraRelay desconectado")
