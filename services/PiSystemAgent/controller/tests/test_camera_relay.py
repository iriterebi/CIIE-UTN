"""Tests de CameraRelay.

No requieren ROS 2: `conftest.py` registra stubs para poder importar el módulo, y
cada test reemplaza `Node`/`Image`/`cv2`/`np` en `camera_relay` con fakes vía
`monkeypatch` (los fakes de cv2/numpy hacen la codificación determinística). El
executor se inyecta (`rclExecutor`) como un fake que registra los nodos.
"""

import asyncio
import types

from controller.camera import camera_relay
from controller.camera.camera_relay import CameraRelay


class _FakeExecutor:
    """Executor compartido falso: registra los nodos que le agregan y quitan."""

    def __init__(self):
        self.nodes: list[object] = []

    def add_node(self, node):
        self.nodes.append(node)
        return True

    def remove_node(self, node):
        self.nodes.remove(node)


def _install_fake_ros(monkeypatch):
    """Reemplaza Node/Image/cv2/np en `camera_relay` con fakes.

    Devuelve `hooks`, un dict con:
      - "Image": la clase falsa de sensor_msgs.msg.Image
      - "on_frame": el callback registrado via create_subscription (se
        llena recién cuando CameraRelay.connect() corre)
    """
    hooks: dict[str, object] = {}

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

    class _FakeArray:
        def __init__(self, data):
            self._data = bytes(data)

        def reshape(self, *shape):
            return self

        def tobytes(self):
            return self._data

    numpy = types.SimpleNamespace(
        uint8="uint8",
        frombuffer=lambda data, dtype: _FakeArray(data),
    )

    class _FakeEncoded:
        def __init__(self, data):
            self._data = data

        def tobytes(self):
            return self._data

    cv2 = types.SimpleNamespace(
        IMWRITE_JPEG_QUALITY=1,
        imencode=lambda ext, frame, params: (True, _FakeEncoded(b"JPEG:" + frame.tobytes())),
    )

    monkeypatch.setattr(camera_relay, "Node", FakeNode)
    monkeypatch.setattr(camera_relay, "Image", Image)
    monkeypatch.setattr(camera_relay, "np", numpy)
    monkeypatch.setattr(camera_relay, "cv2", cv2)

    hooks["Image"] = Image
    return hooks


def _relay(executor=None):
    return CameraRelay(
        node_name="test_camera",
        camera_topic="usb_cam/image_raw",
        jpeg_quality=80,
        rclExecutor=executor if executor is not None else _FakeExecutor(),
    )


def test_connect_adds_node_to_shared_executor(monkeypatch):
    _install_fake_ros(monkeypatch)
    executor = _FakeExecutor()
    relay = _relay(executor)

    async def scenario():
        relay.connect(asyncio.get_running_loop())

    asyncio.run(scenario())
    assert [n.name for n in executor.nodes] == ["test_camera"]


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


def test_disconnect_removes_node_from_executor_and_destroys_it(monkeypatch):
    """Sólo libera su nodo: el contexto rclpy y el executor son de toda la app
    (la strategy local los comparte), así que no los apaga."""
    hooks = _install_fake_ros(monkeypatch)
    executor = _FakeExecutor()
    relay = _relay(executor)

    async def scenario():
        loop = asyncio.get_running_loop()
        relay.connect(loop)
        relay.disconnect()

    asyncio.run(scenario())
    assert executor.nodes == []
    assert hooks.get("destroyed") is True
