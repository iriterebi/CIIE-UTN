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
