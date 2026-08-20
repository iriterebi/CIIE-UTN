# Video de cámara USB en el WebClient Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar el video de la cámara USB de la Pi, en vivo, hasta un `<canvas>` en el WebClient, sin tocar el pipe JSON-RPC existente (`MicroCore`/`UsersXRobotMapType`) ni romper el consumo actual de InOrbit.

**Architecture:** Canal WS binario dedicado, en paralelo al pipe de comandos: `camera_node.py` (ROS 2, ya existe) publica `sensor_msgs/Image` bgr8 → `CameraRelay` (nuevo, PiSystemAgent) lo suscribe por DDS y codifica a JPEG → `VideoWsClient` (nuevo, PiSystemAgent) empuja cada frame por WS a `Api: WS /m2m/robot/video` → `VideoRelay` (nuevo, Api) guarda "último frame gana" → `Api: WS /user/robot/video` lo reenvía al browser → `VideoStream.vue` (nuevo, WebClient) lo pinta en un `<canvas>`. Cero cambios en `MicroCore`, `Strategy`, `handle_json_rpc`, `UsersXRobotMapType` ni nginx (los prefijos `/m2m/` y `/ws/`→`/user/robot/` ya cubren las rutas nuevas).

**Tech Stack:** Python 3.12 (rclpy, opencv, websockets, asyncio) para PiSystemAgent; Python 3.13 (FastAPI, pytest) para Api; Vue 3 + TypeScript (composables) para WebClient.

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md` — toda ambigüedad se resuelve releyendo ese documento.
- No tocar `MicroCore` (`controller/core.py`), ningún `Strategy`, ni `handle_json_rpc` — el video es un canal completamente separado.
- No tocar nginx/`services/Proxy/` ni los quadlets: `location /m2m/` y `location /ws/` (→ `/user/robot/`) ya son prefijos que cubren `/m2m/robot/video` y `/user/robot/video` sin cambios. Verificado en `services/Proxy/nginx.conf` y `nginx.container.conf`.
- Sin buffering ni cola de más de 1 frame en ningún punto del camino — "último frame gana" en todo el pipeline (`CameraRelay`, `VideoRelay` en Api). Si un consumidor va lento, se pisa el frame anterior, nunca se acumula.
- Sin control de vuelta (el usuario no puede pedir resolución/fps/pausa) y sin reconexión "inteligente" del lado Api — cada extremo físico (Pi↔Api, Api↔Browser) maneja su propia reconexión con backoff, igual que ya hace `WsStrategy`/`useRobotSocket.ts` para el pipe de comandos.
- `CameraRelay`/`VideoWsClient` gestionan sus propias credenciales con su propia instancia de `ServerServices`, igual que cualquier strategy — así lo exige `ARQUITECTURA.md` ("Cada strategy debe pedir sus propias credenciales"). No se reutiliza el `ServerServices` privado de `WsStrategy`.
- El video es independiente del `LOCAL_STRATEGY` activo para el brazo — corre en paralelo, no como parte de `Ros2Strategy`. Si `rclpy`/`cv2` no están disponibles (modo demo/mock sin contenedor ROS 2), `CameraRelay` loguea y no arranca — el resto del controller sigue funcionando normal (mismo patrón que `Ros2Controller.connect()`).
- Todos los tests nuevos de Python siguen el patrón ya usado en el repo: `pytest` plano (sin `pytest-asyncio`), cuerpos async envueltos en una función local `async def run(): ...`/`scenario()` ejecutados con `asyncio.run(...)`. Dependencias de ROS 2 (`rclpy`, `sensor_msgs`, `cv2`, `numpy`) se fakean vía `monkeypatch.setitem(sys.modules, ...)`, igual que `controller/tests/test_ros2.py`.
- WebClient no tiene infraestructura de tests automatizados (no hay vitest ni ningún `*.test.*` en el repo) — las tareas de WebClient se verifican manualmente, documentado explícitamente en cada tarea.
- Nueva dependencia: `opencv-python-headless` (PiSystemAgent — `pyproject.toml` y `Dockerfile`, stage `base`). Es la única dependencia nueva del plan; trae `numpy` transitivamente.
- Nota fuera de alcance: `services/PiRobotDriver/Dockerfile` no instala `opencv`/`cv2` pese a que `camera_node.py` ya lo importa — es un gap preexistente del equipo de electrónica, no introducido por este plan y no se toca acá.

---

## Mapa de archivos

**PiRobotDriver (`services/PiRobotDriver/`):**
- Modificar: `agent/camera/camera_node.py`

**PiSystemAgent (`services/PiSystemAgent/`):**
- Modificar: `pyproject.toml`, `Dockerfile`, `.env.defaults`, `controller/config.py`, `controller/main.py`
- Crear: `controller/camera/__init__.py`, `controller/camera/camera_relay.py`, `controller/camera/video_ws_client.py`
- Crear: `controller/tests/test_camera_relay.py`, `controller/tests/test_video_ws_client.py`

**Api (`services/Api/`):**
- Crear: `src/robot/repositories/video_relay.py`, `src/robot/services/user_video_relay.py`
- Modificar: `src/robot/routes/m2m.py`, `src/robot/routes/user.py`
- Crear: `tests/robot/repositories/test_video_relay.py`, `tests/robot/services/test_user_video_relay.py`

**WebClient (`services/WebClient/`):**
- Crear: `src/composables/useVideoSocket.ts`, `src/components/VideoStream.vue`
- Modificar: `src/pages/RobotControlPage.vue`

---

### Task 1: PiRobotDriver — `camera_node.py` publica `bgr8` nativo

**Files:**
- Modify: `services/PiRobotDriver/agent/camera/camera_node.py`

**Interfaces:**
- Consumes: nada.
- Produces: el topic `usb_cam/image_raw` sigue siendo `sensor_msgs/Image`, ahora con `encoding='bgr8'` real (antes decía `bgr8` en `cameraDefinition.yaml` pero publicaba `rgb8`). Consumido por Task 3 (`CameraRelay`).

**Nota:** no hay infraestructura de tests en `PiRobotDriver` (no es parte del workspace `uv`, no tiene `pytest` configurado) — se verifica leyendo el diff y, si hay hardware disponible, corriendo el nodo a mano.

- [ ] **Step 1: Editar `camera_node.py`**

En `services/PiRobotDriver/agent/camera/camera_node.py`, reemplazar el método `publish_frame` completo (elimina la conversión a RGB, que era el bug — `cv2.VideoCapture` ya entrega BGR nativo, y `cameraDefinition.yaml` espera `bgr8`):

```python
    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn('Failed to capture frame')
            return
        h, w, _ = frame.shape
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.height = h
        msg.width = w
        msg.encoding = 'bgr8'
        msg.is_bigendian = False
        msg.step = w * 3
        msg.data = frame.tobytes()
        self.publisher_.publish(msg)
```

- [ ] **Step 2: Verificar el diff**

Run: `cd /home/phosph/personal-proyects/ciie/core/labs-remoto && git diff services/PiRobotDriver/agent/camera/camera_node.py`
Expected: solo se eliminó la línea `frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` y `msg.encoding` cambió de `'rgb8'` a `'bgr8'`. El import `cv2` sigue en uso (por `cv2.VideoCapture`), no queda import muerto.

- [ ] **Step 3: Commit**

```bash
git add services/PiRobotDriver/agent/camera/camera_node.py
git commit -m "fix(pi-robot-driver): camera_node publica bgr8 nativo (coincide con cameraDefinition.yaml)"
```

---

### Task 2: PiSystemAgent — dependencia opencv + config de cámara

**Files:**
- Modify: `services/PiSystemAgent/pyproject.toml`
- Modify: `services/PiSystemAgent/Dockerfile`
- Modify: `services/PiSystemAgent/.env.defaults`
- Modify: `services/PiSystemAgent/controller/config.py`

**Interfaces:**
- Consumes: nada.
- Produces: `config.camera_node_name`, `config.camera_topic`, `config.camera_jpeg_quality` — usados por Task 3 (`CameraRelay`) y Task 5 (`main.py`). `opencv-python-headless` instalado — usado por Task 3.

**Nota:** sin tests — son cambios de dependencias/configuración declarativa, verificados por `uv sync` + import manual.

- [ ] **Step 1: Agregar la dependencia en `pyproject.toml`**

En `services/PiSystemAgent/pyproject.toml`, agregar `"opencv-python-headless>=4.10.0"` a la lista `dependencies` (después de `"websockets>=15.0",`):

```toml
dependencies = [
    "pydantic>=2.11.10",
    "pydantic-settings>=2.13.1",
    "python-dotenv>=1.1.1",
    "requests>=2.32.5",
    "pyserial>=3.5",
    "types-pyserial>=3.5.0.20251001",
    "websockets>=15.0",
    "opencv-python-headless>=4.10.0",
]
```

- [ ] **Step 2: Instalar y verificar**

Run: `cd services/PiSystemAgent && uv sync`
Expected: instala `opencv-python-headless` + `numpy` (dependencia transitiva) sin error.

Run: `cd services/PiSystemAgent && uv run python -c "import cv2, numpy; print(cv2.__version__, numpy.__version__)"`
Expected: imprime dos versiones sin error (confirma que `cv2`/`numpy` están disponibles fuera del contenedor ROS 2 también — necesario porque los tests de Task 3 se corren con `uv run pytest`, no dentro del contenedor).

- [ ] **Step 3: Agregar la dependencia al Dockerfile (stage `base`)**

En `services/PiSystemAgent/Dockerfile`, agregar `"opencv-python-headless"` a la lista de `pip install` del stage `base`:

```dockerfile
 && /opt/venv/bin/pip install --no-cache-dir \
        "pydantic>=2.11.10" \
        "pydantic-settings>=2.13.1" \
        "python-dotenv>=1.1.1" \
        "requests>=2.32.5" \
        "pyserial>=3.5" \
        "websockets>=15.0" \
        "opencv-python-headless>=4.10.0" \
        "pytest>=8.3.0"
```

- [ ] **Step 4: Hornear defaults de cámara en el stage `final`**

En `services/PiSystemAgent/Dockerfile`, agregar al final del stage `final` (después de `ENV ROS2_DOMAIN_ID=42`):

```dockerfile
ENV CAMERA_NODE_NAME=labs_remoto_camera
ENV CAMERA_TOPIC=usb_cam/image_raw
ENV CAMERA_JPEG_QUALITY=80
```

- [ ] **Step 5: Agregar los campos a `Config`**

En `services/PiSystemAgent/controller/config.py`, agregar después del campo `ros2_domain_id` (antes de la línea `config = Config()`):

```python
    camera_node_name: str = Field(
        default='labs_remoto_camera',
        validation_alias=AliasChoices('camera_node_name'),
        description="Nombre del nodo rclpy para la cámara (CameraRelay), distinto del nodo del brazo"
    )

    camera_topic: str = Field(
        default='usb_cam/image_raw',
        validation_alias=AliasChoices('camera_topic'),
        description="Topic ROS 2 de video (sensor_msgs/Image, bgr8) que suscribe CameraRelay"
    )

    camera_jpeg_quality: int = Field(
        default=80,
        validation_alias=AliasChoices('camera_jpeg_quality'),
        description="Calidad JPEG (0-100) usada para codificar cada frame antes de enviarlo"
    )
```

- [ ] **Step 6: Verificar que la config sigue cargando**

Run: `cd services/PiSystemAgent && uv run python -c "from controller.config import config; print(config.camera_node_name, config.camera_topic, config.camera_jpeg_quality)"`
Expected: `labs_remoto_camera usb_cam/image_raw 80` (requiere `.env` con `SERVER_URL`/`ARDUINO_PORT` ya presentes en el repo — si falla por variables faltantes, es preexistente y no de este cambio).

- [ ] **Step 7: Agregar los defaults documentados a `.env.defaults`**

En `services/PiSystemAgent/.env.defaults`, agregar al final:

```bash
# CameraRelay (video de la cámara USB vía ROS 2 → WS dedicado a la Api; ver
# docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md).
# Independiente de LOCAL_STRATEGY: si no hay entorno ROS 2/opencv, no arranca
# y el resto del controller sigue funcionando.
CAMERA_NODE_NAME='labs_remoto_camera'
CAMERA_TOPIC='usb_cam/image_raw'
CAMERA_JPEG_QUALITY=80
```

- [ ] **Step 8: Commit**

```bash
git add services/PiSystemAgent/pyproject.toml services/PiSystemAgent/uv.lock services/PiSystemAgent/Dockerfile services/PiSystemAgent/.env.defaults services/PiSystemAgent/controller/config.py
git commit -m "feat(pi-system-agent): agregar dependencia opencv y config de camara"
```

---

### Task 3: PiSystemAgent — `CameraRelay` (suscriptor ROS 2 → JPEG)

**Files:**
- Create: `services/PiSystemAgent/controller/camera/__init__.py`
- Create: `services/PiSystemAgent/controller/camera/camera_relay.py`
- Test: `services/PiSystemAgent/controller/tests/test_camera_relay.py`

**Interfaces:**
- Consumes: `config.camera_node_name`/`camera_topic`/`camera_jpeg_quality`/`ros2_domain_id` (Task 2), pasados por el caller — `CameraRelay` no importa `config` directamente (mismo desacople que `Ros2Controller`).
- Produces: `CameraRelay(*, node_name: str, camera_topic: str, jpeg_quality: int = 80, domain_id: int = 42)`, `CameraRelay.connect(loop: asyncio.AbstractEventLoop) -> None` (sync, pensado para `run_in_executor`), `CameraRelay.next_frame() -> Awaitable[bytes]`, `CameraRelay.disconnect() -> None`. Usado por Task 5 (`main.py`).

- [ ] **Step 1: Crear el paquete**

Crear `services/PiSystemAgent/controller/camera/__init__.py`:

```python
from .camera_relay import CameraRelay as CameraRelay
```

- [ ] **Step 2: Escribir los tests que fallan**

Crear `services/PiSystemAgent/controller/tests/test_camera_relay.py`:

```python
"""Tests de CameraRelay.

rclpy/sensor_msgs/cv2/numpy se mockean vía sys.modules: estos tests NO
requieren ROS 2 ni opencv instalados de verdad, lo que también verifica
que el import de todos ellos sea diferido (mismo patrón que test_ros2.py).
"""

import asyncio
import sys
import types

import pytest

from controller.camera.camera_relay import CameraRelay


def _install_fake_ros(monkeypatch):
    """Inyecta rclpy/sensor_msgs/cv2/numpy falsos en sys.modules.

    Devuelve `hooks`, un dict con:
      - "Image": la clase falsa de sensor_msgs.msg.Image
      - "on_frame": el callback registrado via create_subscription (se
        llena recién cuando CameraRelay.connect() corre)
    """
    hooks: dict[str, object] = {}
    state = {"ok": False}

    class Image:
        def __init__(self):
            self.data = b""
            self.height = 0
            self.width = 0
            self.encoding = ""

    class FakeNode:
        def __init__(self, name):
            self.name = name

        def create_subscription(self, msg_type, topic, callback, depth):
            hooks["on_frame"] = callback
            hooks["topic"] = topic
            return object()

        def destroy_node(self):
            hooks["destroyed"] = True

    rclpy = types.ModuleType("rclpy")
    rclpy.ok = lambda: state["ok"]
    rclpy.init = lambda *a, **k: state.__setitem__("ok", True)
    rclpy.shutdown = lambda *a, **k: state.__setitem__("ok", False)
    rclpy.spin = lambda node: None  # retorna de inmediato

    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = FakeNode
    rclpy.node = rclpy_node

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.Image = Image
    sensor_msgs.msg = sensor_msgs_msg

    class _FakeArray:
        def __init__(self, data):
            self._data = bytes(data)

        def reshape(self, *shape):
            return self

        def tobytes(self):
            return self._data

    numpy = types.ModuleType("numpy")
    numpy.uint8 = "uint8"
    numpy.frombuffer = lambda data, dtype: _FakeArray(data)

    class _FakeEncoded:
        def __init__(self, data):
            self._data = data

        def tobytes(self):
            return self._data

    cv2 = types.ModuleType("cv2")
    cv2.IMWRITE_JPEG_QUALITY = 1
    cv2.imencode = lambda ext, frame, params: (True, _FakeEncoded(b"JPEG:" + frame.tobytes()))

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy_node)
    monkeypatch.setitem(sys.modules, "sensor_msgs", sensor_msgs)
    monkeypatch.setitem(sys.modules, "sensor_msgs.msg", sensor_msgs_msg)
    monkeypatch.setitem(sys.modules, "numpy", numpy)
    monkeypatch.setitem(sys.modules, "cv2", cv2)

    hooks["Image"] = Image
    hooks["state"] = state
    return hooks


def _relay():
    return CameraRelay(
        node_name="test_camera",
        camera_topic="usb_cam/image_raw",
        jpeg_quality=80,
        domain_id=42,
    )


def test_connect_raises_environment_error_without_rclpy(monkeypatch):
    monkeypatch.setitem(sys.modules, "rclpy", None)  # `import rclpy` -> ImportError
    relay = _relay()

    async def scenario():
        loop = asyncio.get_running_loop()
        with pytest.raises(EnvironmentError):
            relay.connect(loop)

    asyncio.run(scenario())


def test_connect_subscribes_to_configured_topic(monkeypatch):
    hooks = _install_fake_ros(monkeypatch)
    relay = _relay()

    async def scenario():
        loop = asyncio.get_running_loop()
        relay.connect(loop)

    asyncio.run(scenario())
    assert hooks["topic"] == "usb_cam/image_raw"


def test_on_frame_encodes_and_pushes_jpeg(monkeypatch):
    hooks = _install_fake_ros(monkeypatch)
    relay = _relay()
    raw = bytes(range(12))  # 2x2 px, 3 canales

    async def scenario():
        loop = asyncio.get_running_loop()
        relay.connect(loop)

        Image = hooks["Image"]
        msg = Image()
        msg.height, msg.width = 2, 2
        msg.data = raw

        hooks["on_frame"](msg)
        await asyncio.sleep(0)  # deja correr el call_soon_threadsafe

        return await relay.next_frame()

    frame = asyncio.run(scenario())
    assert frame == b"JPEG:" + raw


def test_last_frame_wins_when_not_consumed(monkeypatch):
    hooks = _install_fake_ros(monkeypatch)
    relay = _relay()

    async def scenario():
        loop = asyncio.get_running_loop()
        relay.connect(loop)

        Image = hooks["Image"]
        for raw in (b"a" * 12, b"b" * 12):
            msg = Image()
            msg.height, msg.width = 2, 2
            msg.data = raw
            hooks["on_frame"](msg)
            await asyncio.sleep(0)

        return await relay.next_frame()

    frame = asyncio.run(scenario())
    assert frame == b"JPEG:" + b"b" * 12  # se pisó el frame "a", nunca se acumula


def test_disconnect_shuts_down_rclpy(monkeypatch):
    hooks = _install_fake_ros(monkeypatch)
    relay = _relay()

    async def scenario():
        loop = asyncio.get_running_loop()
        relay.connect(loop)
        relay.disconnect()

    asyncio.run(scenario())
    assert hooks["state"]["ok"] is False
    assert hooks.get("destroyed") is True
```

- [ ] **Step 3: Correr los tests y verificar que fallan**

Run: `cd services/PiSystemAgent && uv run pytest controller/tests/test_camera_relay.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'controller.camera.camera_relay'`

- [ ] **Step 4: Implementar `camera_relay.py`**

Crear `services/PiSystemAgent/controller/camera/camera_relay.py`:

```python
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
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `cd services/PiSystemAgent && uv run pytest controller/tests/test_camera_relay.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add services/PiSystemAgent/controller/camera/__init__.py services/PiSystemAgent/controller/camera/camera_relay.py services/PiSystemAgent/controller/tests/test_camera_relay.py
git commit -m "feat(pi-system-agent): agregar CameraRelay (suscriptor ROS 2 -> JPEG)"
```

---

### Task 4: PiSystemAgent — `VideoWsClient` (push de frames a la Api)

**Files:**
- Create: `services/PiSystemAgent/controller/camera/video_ws_client.py`
- Modify: `services/PiSystemAgent/controller/camera/__init__.py`
- Test: `services/PiSystemAgent/controller/tests/test_video_ws_client.py`

**Interfaces:**
- Consumes: `ServerServices` (ya existe, `server/server_service.py`) — cada instancia es propia de este cliente, no compartida con `WsStrategy`.
- Produces: `VideoWsClient(*, server_service: ServerServices, ws_url: str)`, `VideoWsClient.run(next_frame: Callable[[], Awaitable[bytes]]) -> Never` — usado por Task 5 (`main.py`). `_derive_video_ws_url(server_url: str) -> str` (privado, testeado directo vía import de módulo, mismo patrón que `_derive_ws_url` en `ws_strategy.py`).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `services/PiSystemAgent/controller/tests/test_video_ws_client.py`:

```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from controller.camera import video_ws_client
from controller.camera.video_ws_client import VideoWsClient, _derive_video_ws_url
from controller.server.server_service import ServerServices


def _make_client():
    server_service = ServerServices(
        base_url="http://api.example/m2m/robot/",
        metadata_file="/tmp/unused-robot-metadata.json",
    )
    return VideoWsClient(server_service=server_service, ws_url="ws://api.example/m2m/robot/video")


class _FakeConnection:
    def __init__(self):
        self.sent: list[bytes] = []

    async def send(self, data):
        self.sent.append(data)


class TestDeriveVideoWsUrl:
    @pytest.mark.parametrize("server_url,expected", [
        ("http://api.example/m2m/robot/", "ws://api.example/m2m/robot/video"),
        ("https://api.example/m2m/robot/", "wss://api.example/m2m/robot/video"),
        ("http://api.example/m2m/robot", "ws://api.example/m2m/robot/video"),
    ])
    def test_deriva_ws_url_desde_http(self, server_url, expected):
        assert _derive_video_ws_url(server_url) == expected


class TestRunSendsFrames:
    def test_run_envia_frames_de_next_frame(self):
        client = _make_client()
        client._connect = AsyncMock()
        fake_ws = _FakeConnection()
        client._ws = fake_ws

        frames = [b"frame1", b"frame2"]

        async def next_frame():
            if frames:
                return frames.pop(0)
            await asyncio.sleep(3600)

        async def run():
            task = asyncio.create_task(client.run(next_frame))
            await asyncio.sleep(0.01)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())
        assert fake_ws.sent == [b"frame1", b"frame2"]
        client._connect.assert_awaited_once()


class TestReconnect:
    def test_run_reconecta_tras_conexion_perdida(self, monkeypatch):
        monkeypatch.setattr(video_ws_client, "_MIN_RECONNECT_DELAY", 0.01)
        monkeypatch.setattr(video_ws_client, "_MAX_RECONNECT_DELAY", 0.01)
        client = _make_client()
        connect_calls: list[int] = []

        class _DyingThenAliveConnection:
            def __init__(self, fail: bool):
                self.fail = fail
                self.sent: list[bytes] = []

            async def send(self, data):
                if self.fail:
                    raise ConnectionError("conexión perdida")
                self.sent.append(data)

        async def fake_connect():
            connect_calls.append(1)
            client._ws = _DyingThenAliveConnection(fail=(len(connect_calls) == 1))

        client._connect = fake_connect

        frames = [b"a", b"b"]

        async def next_frame():
            if frames:
                return frames.pop(0)
            await asyncio.sleep(3600)

        async def run():
            task = asyncio.create_task(client.run(next_frame))
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        asyncio.run(run())
        assert len(connect_calls) == 2
        assert client._ws.sent == [b"b"]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/PiSystemAgent && uv run pytest controller/tests/test_video_ws_client.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'controller.camera.video_ws_client'`

- [ ] **Step 3: Implementar `video_ws_client.py`**

Crear `services/PiSystemAgent/controller/camera/video_ws_client.py`:

```python
"""Cliente WS dedicado a video: empuja frames JPEG de CameraRelay a la Api.

Canal separado de WsStrategy/MicroCore (ver
docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md):
push-only, binario, no pasa por el pipe JSON-RPC. Gestiona sus propias
credenciales con su propia instancia de ServerServices — no reutiliza la
de WsStrategy (ver ARQUITECTURA.md: "Cada strategy debe pedir sus propias
credenciales").
"""

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Never

from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidURI

from ..server.server_service import ServerServices

logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0


def _derive_video_ws_url(server_url: str) -> str:
    """Deriva la URL del WS de video a partir de la URL HTTP del servidor.

    http://host/m2m/robot/  → ws://host/m2m/robot/video
    https://host/m2m/robot/ → wss://host/m2m/robot/video

    Mismo esquema que `ws_strategy._derive_ws_url`, pero apuntando a
    `/video` en vez de `/connect`.
    """
    url = server_url.rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url + "/video"


class VideoWsClient:
    def __init__(self, *, server_service: ServerServices, ws_url: str):
        self._server_service = server_service
        self._ws_url = ws_url
        self._ws: ClientConnection | None = None

    async def run(self, next_frame: Callable[[], Awaitable[bytes]]) -> Never:
        """Conecta, reenvía cada frame de `next_frame()`, reconecta ante corte.

        Igual que `WsStrategy.receive`: nunca retorna, el reintento vive
        adentro. Un frame que falla al enviarse (conexión caída) se
        descarta — coherente con "último frame gana", no se bufferiza.
        """
        delay = _MIN_RECONNECT_DELAY
        while True:
            try:
                await self._connect()
                delay = _MIN_RECONNECT_DELAY
                while True:
                    frame = await next_frame()
                    assert self._ws is not None
                    await self._ws.send(frame)
            except (ConnectionClosed, ConnectionError, OSError, InvalidURI) as e:
                logger.warning(
                    "VideoWsClient: conexión perdida (%s), reconectando en %.1fs...",
                    e, delay,
                )
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)

    async def _connect(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)

        self._ws = await connect(self._ws_url)

        challenge_raw = await self._ws.recv()
        challenge: Any = json.loads(challenge_raw)
        if challenge.get("method") != "send_credentials":
            raise ConnectionError(f"Challenge inesperado del servidor: {challenge}")

        assert self._server_service.credentials is not None
        token = self._server_service.credentials.access_token.access_token
        await self._ws.send(json.dumps({"token": token}))

        result_raw = await self._ws.recv()
        result: Any = json.loads(result_raw)
        if result.get("status") != "success auth":
            raise ConnectionError(f"Auth WS de video fallido: {result}")

        logger.info("VideoWsClient: auth WS exitoso")

    def _authenticate(self) -> None:
        """Ejecuta registro + handshake HTTP (sync, corre en executor)."""
        self._server_service.load_config()
        if not self._server_service.connect_with_retry():
            raise EnvironmentError("VideoWsClient: no se pudo autenticar con el servidor.")
```

Modificar `services/PiSystemAgent/controller/camera/__init__.py`:

```python
from .camera_relay import CameraRelay as CameraRelay
from .video_ws_client import VideoWsClient as VideoWsClient
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/PiSystemAgent && uv run pytest controller/tests/test_video_ws_client.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add services/PiSystemAgent/controller/camera/video_ws_client.py services/PiSystemAgent/controller/camera/__init__.py services/PiSystemAgent/controller/tests/test_video_ws_client.py
git commit -m "feat(pi-system-agent): agregar VideoWsClient (push de frames JPEG a la Api)"
```

---

### Task 5: PiSystemAgent — wiring en `main.py`

**Files:**
- Modify: `services/PiSystemAgent/controller/main.py`

**Interfaces:**
- Consumes: `CameraRelay`/`VideoWsClient` (Tasks 3-4), `config.camera_*` (Task 2), `ServerServices` (ya existe).
- Produces: nada consumido por otra tarea (es el entry point).

**Nota:** orquestación pura sobre piezas ya testeadas — sin test automatizado nuevo (mismo criterio que `m2m.py` en el plan de resiliencia-reconexión: routing/wiring se verifica con un smoke test manual). Requiere el contenedor ROS 2 (`make ros.run` o similar) para probarse de punta a punta; en modo mock (`uv run python -m controller`, sin ROS 2 sourceado) el camino esperado es que loguee y siga funcionando el resto del controller.

- [ ] **Step 1: Modificar `main.py`**

Reemplazar el contenido completo de `services/PiSystemAgent/controller/main.py`:

```python
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
```

- [ ] **Step 2: Correr toda la suite para descartar regresiones**

Run: `cd services/PiSystemAgent && uv run pytest -v`
Expected: PASS (todos los tests, incluyendo los de Tasks 3-4)

- [ ] **Step 3: Smoke test manual en modo mock (sin ROS 2)**

```bash
cd services/PiSystemAgent
MOCK_ROBOT=1 CREATE_DEFAULT_METADATA=1 uv run python -m controller
```

Expected en los logs: el controller arranca normal (`Micro core iniciado`), y aparece `Cámara no disponible, video deshabilitado: ...` (porque no hay `rclpy`/`cv2` de ROS 2 sourceados fuera del contenedor) sin que el proceso se caiga ni afecte `MockStrategy`. Ctrl+C para detener.

- [ ] **Step 4: Smoke test manual con el contenedor ROS 2 (si hay cámara/hardware disponible)**

Con el agente ROS de `PiRobotDriver` corriendo (`camera_node.py` de Task 1) y una Api + robot aprobado disponibles:

```bash
cd services/PiSystemAgent && make ros.run
```

Expected: en los logs aparece `CameraRelay conectado (...)` y `VideoWsClient: auth WS exitoso`; en la Api, la conexión WS entrante en `/m2m/robot/video` (visible una vez completada Task 7).

- [ ] **Step 5: Commit**

```bash
git add services/PiSystemAgent/controller/main.py
git commit -m "feat(pi-system-agent): correr el pipeline de video en paralelo al MicroCore"
```

---

### Task 6: Api — `VideoRelay` + `VideoRelayRepository`

**Files:**
- Create: `services/Api/src/robot/repositories/video_relay.py`
- Test: `services/Api/tests/robot/repositories/test_video_relay.py`

**Interfaces:**
- Consumes: nada.
- Produces: `VideoRelay.push_frame(frame: bytes) -> None`, `VideoRelay.next_frame() -> Awaitable[bytes]`, `VideoRelayRepository.get_or_create(robot_id: str) -> VideoRelay`, `VideoRelayRepository.discard(robot_id: str) -> None`, `VideoRelayRepositoryDep`. Usado por Task 7 (`m2m.py`) y Task 8 (`UserVideoRelay`).

- [ ] **Step 1: Escribir los tests que fallan**

Crear `services/Api/tests/robot/repositories/test_video_relay.py`:

```python
import asyncio

from src.robot.repositories.video_relay import VideoRelay, VideoRelayRepository


class TestVideoRelay:
    def test_push_luego_next_frame_entrega_el_mismo_frame(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"frame1")
            return await relay.next_frame()

        assert asyncio.run(run()) == b"frame1"

    def test_next_frame_espera_hasta_que_llega_un_frame(self):
        relay = VideoRelay()

        async def run():
            async def _push_later():
                await asyncio.sleep(0.01)
                relay.push_frame(b"tardio")

            waiter = asyncio.create_task(relay.next_frame())
            pusher = asyncio.create_task(_push_later())
            result = await waiter
            await pusher
            return result

        assert asyncio.run(run()) == b"tardio"

    def test_ultimo_frame_gana_si_no_se_consume(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"a")
            relay.push_frame(b"b")
            return await relay.next_frame()

        assert asyncio.run(run()) == b"b"

    def test_frames_no_se_acumulan_tras_consumir(self):
        relay = VideoRelay()

        async def run():
            relay.push_frame(b"a")
            first = await relay.next_frame()

            async def _push_later():
                await asyncio.sleep(0.01)
                relay.push_frame(b"b")

            waiter = asyncio.create_task(relay.next_frame())
            pusher = asyncio.create_task(_push_later())
            second = await waiter
            await pusher
            return first, second

        assert asyncio.run(run()) == (b"a", b"b")


class TestVideoRelayRepository:
    def test_get_or_create_retorna_la_misma_instancia(self):
        repo = VideoRelayRepository()

        first = repo.get_or_create("robot-1")
        second = repo.get_or_create("robot-1")

        assert first is second

    def test_robots_distintos_tienen_relays_independientes(self):
        repo = VideoRelayRepository()

        relay_a = repo.get_or_create("robot-a")
        relay_b = repo.get_or_create("robot-b")

        assert relay_a is not relay_b

    def test_discard_remueve_el_relay(self):
        repo = VideoRelayRepository()
        first = repo.get_or_create("robot-1")

        repo.discard("robot-1")
        second = repo.get_or_create("robot-1")

        assert first is not second

    def test_discard_sobre_robot_inexistente_es_noop(self):
        repo = VideoRelayRepository()
        repo.discard("no-existe")  # no debe lanzar
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_video_relay.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.robot.repositories.video_relay'`

- [ ] **Step 3: Implementar `video_relay.py`**

Crear `services/Api/src/robot/repositories/video_relay.py`:

```python
"""Relay de video 1:1 por robot: último frame gana.

Ver docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
No es un StreamSource/StreamConnection (esos existen para el pipe JSON-RPC
de comandos, ver stream_entities.py): es un canal push-only, sin heartbeat
ni reconexión propia — cada lado (Pi, browser) maneja su propia reconexión
física de forma independiente.
"""

import asyncio
import functools
from typing import Annotated

from fastapi import Depends


class VideoRelay:
    """Cola de capacidad 1: pisa el frame anterior si nadie lo consumió."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=1)

    def push_frame(self, frame: bytes) -> None:
        if self._queue.full():
            _ = self._queue.get_nowait()
        self._queue.put_nowait(frame)

    async def next_frame(self) -> bytes:
        return await self._queue.get()


class VideoRelayRepository:
    def __init__(self) -> None:
        self._relays: dict[str, VideoRelay] = {}

    def get_or_create(self, robot_id: str) -> VideoRelay:
        if robot_id not in self._relays:
            self._relays[robot_id] = VideoRelay()
        return self._relays[robot_id]

    def discard(self, robot_id: str) -> None:
        _ = self._relays.pop(robot_id, None)


@functools.cache
def get_video_relay_repository() -> VideoRelayRepository:
    return VideoRelayRepository()


VideoRelayRepositoryDep = Annotated[VideoRelayRepository, Depends(get_video_relay_repository)]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_video_relay.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add services/Api/src/robot/repositories/video_relay.py services/Api/tests/robot/repositories/test_video_relay.py
git commit -m "feat(api): agregar VideoRelay/VideoRelayRepository (ultimo frame gana)"
```

---

### Task 7: Api — `WS /m2m/robot/video`

**Files:**
- Modify: `services/Api/src/robot/routes/m2m.py`

**Interfaces:**
- Consumes: `VideoRelayRepositoryDep` (Task 6), `HandshakeServiceDep`/`RobotStreamAutentication` (ya existen, mismos usados por `/connect`).
- Produces: nada consumido por otra tarea (punto de entrada de la Pi).

**Nota de diseño:** el bloque de autenticación (challenge `send_credentials` → JWT → `success auth`) se duplica intencionalmente en vez de extraerlo a un helper compartido con `/connect` — `/connect` ya está testeado end-to-end (heartbeat, `clean_close` vs `timeout`) y diverge fuerte después del auth; forzar un helper común arriesgaría ese código a cambio de ahorrar ~15 líneas. Sin test automatizado nuevo (mismo criterio que el resto de `m2m.py`: routing es orquestación, se verifica con smoke test manual).

- [ ] **Step 1: Agregar el endpoint `/video` a `m2m.py`**

En `services/Api/src/robot/routes/m2m.py`, agregar el import de `VideoRelayRepositoryDep` (junto a los imports existentes de `..repositories.robot_connection`):

```python
from ..repositories.robot_connection import RobotConnectionRepositoryDep
from ..repositories.video_relay import VideoRelayRepositoryDep
```

Agregar el nuevo endpoint al final del archivo (después de la función `robot_connection`):

```python
@router.websocket('/video')
async def robot_video(
    websocket: WebSocket,
    video_relay_repository: VideoRelayRepositoryDep,
    robot_handshake_service: HandshakeServiceDep,
):
    """Canal de video separado de `/connect`: push-only, binario, sin pasar
    por el pipe JSON-RPC. Ver docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
    """
    await websocket.accept()

    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "send_credentials",
        "params": [],
        "id": 1,
    })

    robot: Robot | None
    try:
        access_bare_data: dict[str, Any] = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny, reportExplicitAny]
        access_data = RobotStreamAutentication.model_validate(access_bare_data)
        robot = robot_handshake_service.get_robot_by_token(access_data.token)
    except Exception as e:
        logger.error(e)
        await websocket.send_json({"status": "error", "message": "Error validating token"})
        await websocket.close()
        return

    if robot is None:
        await websocket.send_json({"status": "error", "message": "Robot not found"})
        await websocket.close()
        return

    await websocket.send_json({"status": "success auth"})

    relay = video_relay_repository.get_or_create(str(robot.id))

    try:
        while True:
            frame: bytes = await websocket.receive_bytes()
            relay.push_frame(frame)
    except Exception as e:
        logger.info("Conexión de video del robot %s cerrada: %s", robot.id, e)
    finally:
        video_relay_repository.discard(str(robot.id))
```

- [ ] **Step 2: Correr toda la suite de Api para descartar regresiones**

Run: `cd services/Api && uv run pytest -v`
Expected: PASS (todos los tests existentes + los de Task 6)

- [ ] **Step 3: Smoke test manual**

Con la Api corriendo (`cd services/Api && make up_dev`) y un robot aprobado, usar un script chico ad-hoc (o `websocat`/`wscat` si están disponibles) para conectar a `ws://localhost:8000/m2m/robot/video`, completar el challenge con un JWT de robot válido (obtenido vía `/m2m/robot/handshake`), y confirmar que llega `{"status": "success auth"}`. Enviar un frame binario cualquiera (`websocat --binary` con un archivo) y verificar en los logs de la Api que no hay excepciones.

- [ ] **Step 4: Commit**

```bash
git add services/Api/src/robot/routes/m2m.py
git commit -m "feat(api): agregar WS /m2m/robot/video para recibir frames de la Pi"
```

---

### Task 8: Api — `UserVideoRelay` + `WS /user/robot/video`

**Files:**
- Create: `services/Api/src/robot/services/user_video_relay.py`
- Modify: `services/Api/src/robot/routes/user.py`
- Test: `services/Api/tests/robot/services/test_user_video_relay.py`

**Interfaces:**
- Consumes: `VideoRelayRepositoryDep` (Task 6), `AccessValidator`/`RobotServiceDep`/`UserServiceDep` (ya existen, mismos usados por `UserToRobotComunication`).
- Produces: `UserVideoRelayDep` — usado por `routes/user.py`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `services/Api/tests/robot/services/test_user_video_relay.py`:

```python
import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

from src.robot.entities import Robot
from src.robot.entities.errors import RobotAccessException
from src.robot.repositories.video_relay import VideoRelayRepository
from src.robot.services.access_validator import AccessValidator
from src.robot.services.user_video_relay import UserVideoRelay
from src.auth.entities import User


def _make_robot():
    r = MagicMock(spec=Robot)
    r.id = uuid4()
    return r


def _make_user():
    u = MagicMock(spec=User)
    u.usr_name = "juan"
    return u


class _FakeWebSocket:
    def __init__(self, incoming, *, stop_after: int = 999):
        self._incoming = incoming
        self._stop_after = stop_after
        self.sent_json = []
        self.sent_bytes = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        return self._incoming

    async def send_json(self, data):
        self.sent_json.append(data)

    async def send_bytes(self, data):
        self.sent_bytes.append(data)
        if len(self.sent_bytes) >= self._stop_after:
            raise ConnectionError("simulated client disconnect")

    async def close(self):
        self.closed = True


def _make_relay_service(robot, *, grant_access=True):
    robot_service = MagicMock()
    robot_service.get_robot_by_id.return_value = robot

    user_service = MagicMock()
    user_service.get_user_by_token.return_value = _make_user()

    access_validator = MagicMock(spec=AccessValidator)
    if grant_access:
        access_validator.validate_grant_access.return_value = None
    else:
        access_validator.validate_grant_access.side_effect = RobotAccessException(str(robot.id))

    video_relay_repository = VideoRelayRepository()

    service = UserVideoRelay(robot_service, access_validator, video_relay_repository, user_service)
    return service, video_relay_repository


class TestUserVideoRelayConnectWs:
    def test_reenvia_frames_del_relay_hasta_que_el_cliente_se_va(self):
        robot = _make_robot()
        service, repo = _make_relay_service(robot)
        ws = _FakeWebSocket({"token": "tok", "robot_id": str(robot.id)}, stop_after=2)

        async def run():
            relay = repo.get_or_create(str(robot.id))

            # VideoRelay tiene capacidad 1 ("último frame gana" — ver Task 6):
            # empujar frame1 y frame2 sincrónicamente, antes de que connect_ws
            # arranque a consumir, pisaría frame1 y el test se colgaría
            # esperando un segundo frame que nunca llega. Se intercalan los
            # pushes con la propia espera de connect_ws en relay.next_frame():
            # connect_ws no tiene ninguna suspensión real antes de ese primer
            # await (accept/receive_json/validate son todos instantáneos
            # contra los fakes), así que ya está bloqueado en next_frame()
            # para cuando el primer sleep(0.01) del pusher vence — frame1
            # siempre llega a una cola vacía.
            async def push_frames():
                await asyncio.sleep(0.01)
                relay.push_frame(b"frame1")
                await asyncio.sleep(0.01)
                relay.push_frame(b"frame2")

            pusher = asyncio.create_task(push_frames())
            await service.connect_ws(ws)
            await pusher

        asyncio.run(run())

        assert ws.accepted is True
        assert {"message": "success auth"} in ws.sent_json
        assert ws.sent_bytes == [b"frame1", b"frame2"]

    def test_sin_grant_access_no_reenvia_frames(self):
        robot = _make_robot()
        service, repo = _make_relay_service(robot, grant_access=False)
        ws = _FakeWebSocket({"token": "tok", "robot_id": str(robot.id)})

        async def run():
            await service.connect_ws(ws)

        asyncio.run(run())

        assert ws.sent_bytes == []
        assert {"message": "success auth"} not in ws.sent_json
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/Api && uv run pytest tests/robot/services/test_user_video_relay.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.robot.services.user_video_relay'`

- [ ] **Step 3: Implementar `user_video_relay.py`**

Crear `services/Api/src/robot/services/user_video_relay.py`:

```python
"""Relay de video usuario↔robot: canal WS separado del pipe de comandos.

Ver docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
Valida el mismo token robot_access que /user/robot/send_command (mismo
control de acceso), pero no pasa por UsersXRobotMapType — es push-only,
sin heartbeat propio. Si el socket muere, el browser reconecta directo,
sin necesitar avisar al pipe de comandos.
"""

import asyncio
import functools
import logging
from typing import Annotated, final

from fastapi import Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..entities.errors import UserValidationTimeoutException
from ..entities.json_rpc_commands import UserWsAuthentication
from ..repositories.video_relay import VideoRelayRepository, VideoRelayRepositoryDep
from .access_validator import AccessValidator, UserRobotAccessSession
from .robot_service import RobotService, RobotServiceDep
from ...auth.services import UserService, UserServiceDep

logger = logging.getLogger(__name__)


@final
class UserVideoRelay:
    def __init__(
        self,
        robot_service: RobotService,
        access_validator: AccessValidator,
        video_relay_repository: VideoRelayRepository,
        user_service: UserService,
    ):
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.video_relay_repository = video_relay_repository
        self.user_service = user_service

    async def connect_ws(self, websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny]
            entity = UserWsAuthentication.model_validate(result)

            user = self.user_service.get_user_by_token(entity.token)
            robot = self.robot_service.get_robot_by_id(entity.robot_id)
            if user is None or robot is None:
                raise UserValidationTimeoutException()

            self.access_validator.validate_grant_access(
                entity.token, entity.robot_id, UserRobotAccessSession(user.usr_name),
            )

            await websocket.send_json({"message": "success auth"})

            relay = self.video_relay_repository.get_or_create(str(robot.id))
            while True:
                frame = await relay.next_frame()
                await websocket.send_bytes(frame)

        except (WebSocketDisconnect, asyncio.TimeoutError):
            logger.info("Conexión de video de usuario cerrada")
        except Exception as e:
            logger.error("Error en video de usuario: %s", e, exc_info=e)
            try:
                await websocket.close()
            except Exception:
                pass


@functools.cache
def create_user_video_relay(
    robot_service: RobotServiceDep,
    access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
    video_relay_repository: VideoRelayRepositoryDep,
    user_service: UserServiceDep,
) -> UserVideoRelay:
    return UserVideoRelay(robot_service, access_validator, video_relay_repository, user_service)


UserVideoRelayDep = Annotated[UserVideoRelay, Depends(create_user_video_relay)]
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/Api && uv run pytest tests/robot/services/test_user_video_relay.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Conectar el endpoint en `routes/user.py`**

Reemplazar el contenido completo de `services/Api/src/robot/routes/user.py`:

```python
from fastapi import APIRouter
from starlette.websockets import WebSocket

from ..services.ipc_user_robot_comunication import RobotIPCDep
from ..services.user_video_relay import UserVideoRelayDep

router = APIRouter(tags=["robots", "user"])


@router.websocket("/send_command")
async def send_command_ws(
        websocket: WebSocket,
        ipc: RobotIPCDep,
):
    await ipc.connect_ws(websocket)


@router.websocket("/video")
async def video_ws(
        websocket: WebSocket,
        video_relay: UserVideoRelayDep,
):
    await video_relay.connect_ws(websocket)
```

- [ ] **Step 6: Correr toda la suite de Api para descartar regresiones**

Run: `cd services/Api && uv run pytest -v`
Expected: PASS (todos los tests)

- [ ] **Step 7: Commit**

```bash
git add services/Api/src/robot/services/user_video_relay.py services/Api/src/robot/routes/user.py services/Api/tests/robot/services/test_user_video_relay.py
git commit -m "feat(api): agregar UserVideoRelay y WS /user/robot/video"
```

---

### Task 9: WebClient — `useVideoSocket` + `VideoStream.vue`

**Files:**
- Create: `services/WebClient/src/composables/useVideoSocket.ts`
- Create: `services/WebClient/src/components/VideoStream.vue`
- Modify: `services/WebClient/src/pages/RobotControlPage.vue`

**Interfaces:**
- Consumes: nada del backend directamente en tiempo de compilación — se conecta en runtime a `WS /user/robot/video` (mismo `WS_BASE`/proxy que `useRobotSocket.ts`).
- Produces: nada consumido por otro archivo de este plan (hoja del árbol de dependencias).

**Nota:** sin infraestructura de tests en WebClient (ver Global Constraints) — se verifica manualmente en el navegador.

- [ ] **Step 1: Crear `useVideoSocket.ts`**

Crear `services/WebClient/src/composables/useVideoSocket.ts`:

```typescript
import { readonly, ref } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''

export type VideoStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting' | 'error'

const MIN_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

export function useVideoSocket() {
  const status = ref<VideoStatus>('disconnected')
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let canvasCtx: CanvasRenderingContext2D | null = null
  let robotId: string | null = null
  let robotAccessToken: string | null = null
  let manualDisconnect = false
  let authFailed = false
  let reconnectDelayMs = MIN_RECONNECT_DELAY_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let painting = false

  function scheduleReconnect() {
    if (manualDisconnect || authFailed || reconnectTimer !== null) return
    status.value = 'reconnecting'
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (robotId && robotAccessToken && canvasCtx) connect(robotId, robotAccessToken, canvasCtx)
    }, reconnectDelayMs)
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS)
  }

  async function paintFrame(blob: Blob) {
    // Descarta el frame si todavía se está pintando el anterior — mismo
    // criterio "último frame gana" que el resto del canal de video.
    if (painting || !canvasCtx) return
    painting = true
    try {
      const bitmap = await createImageBitmap(blob)
      canvasCtx.canvas.width = bitmap.width
      canvasCtx.canvas.height = bitmap.height
      canvasCtx.drawImage(bitmap, 0, 0)
      bitmap.close()
    } finally {
      painting = false
    }
  }

  function connect(_robotId: string, _robotAccessToken: string, ctx: CanvasRenderingContext2D) {
    manualDisconnect = false
    authFailed = false
    robotId = _robotId
    robotAccessToken = _robotAccessToken
    canvasCtx = ctx
    status.value = 'connecting'
    error.value = null

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}${WS_BASE}/user/robot/video`

    ws = new WebSocket(wsUrl)
    ws.binaryType = 'blob'

    ws.onopen = () => {
      status.value = 'authenticating'
      ws!.send(JSON.stringify({ token: robotAccessToken, robot_id: robotId }))
    }

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof Blob) {
        if (status.value !== 'connected') {
          status.value = 'connected'
          reconnectDelayMs = MIN_RECONNECT_DELAY_MS
        }
        void paintFrame(event.data)
        return
      }

      const data = JSON.parse(event.data)
      if (status.value === 'authenticating' && data.message !== 'success auth') {
        status.value = 'error'
        error.value = data.message || 'Error de autenticación de video'
        authFailed = true
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      error.value = 'Error de conexión de video'
    }

    ws.onclose = () => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      if (manualDisconnect) {
        status.value = 'disconnected'
        return
      }
      if (authFailed) {
        status.value = 'error'
        return
      }
      scheduleReconnect()
    }
  }

  function disconnect() {
    manualDisconnect = true
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
  }

  return {
    status: readonly(status),
    error,
    connect,
    disconnect,
  }
}
```

- [ ] **Step 2: Crear `VideoStream.vue`**

Crear `services/WebClient/src/components/VideoStream.vue`:

```vue
<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useVideoSocket } from '../composables/useVideoSocket'

const props = defineProps<{
  robotId: string
  robotAccessToken: string
  active: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const { status, error, connect, disconnect } = useVideoSocket()

watch(
  () => props.active,
  (active) => {
    if (active && canvasRef.value) {
      const ctx = canvasRef.value.getContext('2d')
      if (ctx) connect(props.robotId, props.robotAccessToken, ctx)
    } else {
      disconnect()
    }
  },
  { immediate: true }
)

onUnmounted(() => disconnect())
</script>

<template>
  <div>
    <canvas ref="canvasRef" style="max-width: 100%; background: #000;"></canvas>
    <p v-if="status !== 'connected'">
      <small v-if="status === 'error'">Video: {{ error }}</small>
      <small v-else>Video: {{ status }}...</small>
    </p>
  </div>
</template>
```

- [ ] **Step 3: Conectar `VideoStream` en `RobotControlPage.vue`**

En `services/WebClient/src/pages/RobotControlPage.vue`, agregar el import (junto a `RobotCommandPanel`):

```typescript
import VideoStream from '../components/VideoStream.vue'
```

Agregar el componente al template, antes de `<RobotCommandPanel ... />`:

```html
  <VideoStream
    v-if="robotAccessToken"
    :robot-id="robotId"
    :robot-access-token="robotAccessToken"
    :active="status === 'connected'"
  />

  <RobotCommandPanel
```

- [ ] **Step 4: Verificar el build de tipos**

Run: `cd services/WebClient && npm run build`
Expected: `vue-tsc -b` pasa sin errores de tipos, `vite build` genera `dist/` sin fallar.

- [ ] **Step 5: Verificación manual end-to-end**

Con la Api, el WebClient (`npm run dev`) y un `PiSystemAgent` con `Ros2Strategy`/cámara real corriendo (Tasks 1-8 completas):

1. Loguearse, entrar a `/robot/:id` de un robot con cámara.
2. Verificar que el `<canvas>` muestra el video en vivo, con colores correctos (post fix de Task 1 — no debe verse azul/rojo invertido).
3. Cortar el proceso `PiSystemAgent` y confirmar que el video se congela y el WebClient no rompe (el pipe de comandos sigue su propio flujo de reconexión ya existente, ver `docs/superpowers/specs/2026-07-06-resiliencia-reconexion-design.md`).
4. Recargar la página y confirmar que el video reconecta solo.

- [ ] **Step 6: Commit**

```bash
git add services/WebClient/src/composables/useVideoSocket.ts services/WebClient/src/components/VideoStream.vue services/WebClient/src/pages/RobotControlPage.vue
git commit -m "feat(webclient): mostrar el video de la camara en RobotControlPage"
```

---
