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
import threading
from typing import Any

logger = logging.getLogger(__name__)


class CameraRelay:
    """Último frame gana: la cola tiene capacidad 1, se pisa el anterior si
    nadie lo consumió (ver Global Constraints del plan — sin buffering)."""

    def __init__(self, *, node_name: str, camera_topic: str, jpeg_quality: int = 80, domain_id: int = 42):
        self.node_name = node_name
        self.camera_topic = camera_topic
        self.jpeg_quality = jpeg_quality
        self.domain_id = domain_id

        self._rclpy: Any = None
        self._cv2: Any = None
        self._np: Any = None
        self._node: Any = None
        self._spin_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)

        self.logger = logging.getLogger(__name__)

    def connect(self, loop: asyncio.AbstractEventLoop) -> None:
        """Sync — pensado para correr en `run_in_executor` (mismo patrón que
        `Ros2Controller.connect`). Recibe `loop` explícito porque se llama
        desde un worker thread, donde `asyncio.get_running_loop()` no ve el
        loop del thread principal.
        """
        os.environ.setdefault("ROS_DOMAIN_ID", str(self.domain_id))
        try:
            import rclpy  # import diferido: requiere entorno ROS 2 sourceado
            from rclpy.node import Node
            from sensor_msgs.msg import Image
            import cv2
            import numpy as np
        except ImportError as e:
            raise EnvironmentError(
                "No se pudo importar rclpy/sensor_msgs/cv2/numpy. Asegúrate de "
                "sourcear el entorno ROS 2 y tener opencv instalado antes de "
                "usar CameraRelay."
            ) from e

        self._rclpy = rclpy
        self._cv2 = cv2
        self._np = np
        self._loop = loop

        if not rclpy.ok():
            rclpy.init()

        self._node = Node(self.node_name)
        self._node.create_subscription(Image, self.camera_topic, self._on_frame, 10)

        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()
        self.logger.info(
            "CameraRelay conectado (node=%s, domain=%s, topic=%s)",
            self.node_name, os.environ.get("ROS_DOMAIN_ID"), self.camera_topic,
        )

    def _spin(self) -> None:
        try:
            self._rclpy.spin(self._node)
        except Exception as e:  # spin levanta al hacer shutdown; fin normal
            self.logger.debug("rclpy.spin finalizó: %s", e)

    def _on_frame(self, msg: Any) -> None:
        """Callback de ROS 2 (corre en el thread de spin). Codifica bgr8 → JPEG."""
        frame = self._np.frombuffer(msg.data, dtype=self._np.uint8).reshape(
            msg.height, msg.width, 3
        )
        ok, encoded = self._cv2.imencode(
            ".jpg", frame, [self._cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not ok:
            self.logger.warning("No se pudo codificar el frame a JPEG")
            return

        jpeg_bytes = encoded.tobytes()
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._push, jpeg_bytes)

    def _push(self, jpeg_bytes: bytes) -> None:
        """Corre en el loop asyncio (vía call_soon_threadsafe)."""
        if self._queue.full():
            _ = self._queue.get_nowait()
        self._queue.put_nowait(jpeg_bytes)

    async def next_frame(self) -> bytes:
        return await self._queue.get()

    def disconnect(self) -> None:
        if self._rclpy is not None and self._rclpy.ok():
            self._rclpy.shutdown()
        if self._spin_thread is not None and self._spin_thread.is_alive():
            self._spin_thread.join(timeout=2)
        if self._node is not None:
            try:
                self._node.destroy_node()
            except Exception as e:
                self.logger.debug("destroy_node falló: %s", e)
        self.logger.info("CameraRelay desconectado")
