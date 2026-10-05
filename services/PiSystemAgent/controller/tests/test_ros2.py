"""Tests del controlador/strategy ROS 2.

rclpy se mockea vía sys.modules: estos tests NO requieren ROS 2 instalado, lo que
también verifica que el import de rclpy sea diferido (el módulo se importa sin él).
"""

import asyncio
import os
import sys
import types

import pytest

from controller.robot import ros2_controller
from controller.robot.responses import (
    CommandsDescriptionRobotResponse, InvalidCommandError,
)
from controller.robot.ros2_controller import Ros2Controller, parse_key_value
from controller.strategy.local.ros2_strategy import Ros2Strategy


# --- Fake rclpy / std_msgs ---

def _install_fake_ros(monkeypatch):
    """Inyecta un rclpy/std_msgs falso en sys.modules. Devuelve (published, hooks)."""
    published: list[str] = []
    hooks: dict[str, object] = {}
    state = {"ok": False}

    class String:
        def __init__(self):
            self.data = ""

    class FakePublisher:
        def publish(self, msg):
            published.append(msg.data)

    class FakeNode:
        def __init__(self, name):
            self.name = name

        def create_publisher(self, msg_type, topic, depth):
            return FakePublisher()

        def create_subscription(self, msg_type, topic, callback, depth):
            hooks["on_data"] = callback
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

    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.String = String
    std_msgs.msg = std_msgs_msg

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy_node)
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", std_msgs_msg)

    hooks["String"] = String
    hooks["state"] = state
    return published, hooks


def _controller(domain_id=42):
    return Ros2Controller(
        node_name="test_node",
        command_topic="cmd",
        data_topic="data",
        domain_id=domain_id,
    )


# --- parse_key_value ---

@pytest.mark.parametrize("raw,expected", [
    ("base=90", {"base": "90"}),
    ("base=90, mano=10", {"base": "90", "mano": "10"}),
    ("base=90; mano=10 hombro=45", {"base": "90", "mano": "10", "hombro": "45"}),
    ("base=90 junk sin_igual", {"base": "90"}),
    ("", {}),
    ("=novalue valido=1", {"valido": "1"}),
])
def test_parse_key_value(raw, expected):
    assert parse_key_value(raw) == expected


# --- Ros2Controller ---

def test_connect_raises_environment_error_without_rclpy(monkeypatch):
    monkeypatch.setitem(sys.modules, "rclpy", None)  # `import rclpy` -> ImportError
    ctrl = _controller()
    with pytest.raises(EnvironmentError):
        ctrl.connect()


def test_send_command_publishes(monkeypatch):
    published, _ = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.send_command("base=90")
    assert published == ["base=90"]


def test_connect_sets_ros_domain_id(monkeypatch):
    monkeypatch.delenv("ROS_DOMAIN_ID", raising=False)
    _install_fake_ros(monkeypatch)
    ctrl = _controller(domain_id=42)
    ctrl.connect()
    assert os.environ["ROS_DOMAIN_ID"] == "42"


def test_connect_respects_external_ros_domain_id(monkeypatch):
    monkeypatch.setenv("ROS_DOMAIN_ID", "7")  # externo gana (setdefault)
    _install_fake_ros(monkeypatch)
    ctrl = _controller(domain_id=42)
    ctrl.connect()
    assert os.environ["ROS_DOMAIN_ID"] == "7"


def test_send_command_without_connect_raises():
    ctrl = _controller()
    with pytest.raises(ConnectionError):
        ctrl.send_command("base=90")


def test_execute_sequence_publishes_in_order(monkeypatch):
    published, _ = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.execute_sequence(["a=1", "", "b=2"])
    assert published == ["a=1", "b=2"]


def test_on_data_updates_telemetry_snapshot(monkeypatch):
    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    String = hooks["String"]
    msg = String()
    msg.data = "base=90 mano=10"
    hooks["on_data"](msg)
    status = ctrl.get_status()
    assert status["telemetry"] == {"base": "90", "mano": "10"}
    assert status["mock"] is False
    assert status["node"] == "test_node"


def test_get_status_reflects_connection(monkeypatch):
    _, _ = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    assert ctrl.get_status()["status"] == "disconnected"
    ctrl.connect()
    assert ctrl.get_status()["status"] == "online"
    ctrl.disconnect()
    assert ctrl.get_status()["status"] == "disconnected"


# --- Autodescubrimiento de comandos ---

def test_on_data_does_not_propagate_to_spin_thread(monkeypatch):
    """Una excepción en el callback mataría el spin en silencio: debe quedar contenida."""
    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()

    def boom(_serialiced):
        raise RuntimeError("parser roto")

    monkeypatch.setattr(ros2_controller, "parse_commands", boom)

    String = hooks["String"]
    msg = String()
    msg.data = "commands=restart"
    hooks["on_data"](msg)  # no debe levantar

    msg2 = String()
    msg2.data = "base=90"
    hooks["on_data"](msg2)
    assert ctrl.get_status()["telemetry"] == {"base": "90"}


def test_send_command_raises_on_unknown_command(monkeypatch):
    published, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()

    String = hooks["String"]
    msg = String()
    msg.data = "commands=restart,<toggle:start|stop>play"
    hooks["on_data"](msg)

    with pytest.raises(InvalidCommandError):
        ctrl.send_command("jump")
    assert published == []

    ctrl.send_command("start")
    assert published == ["start"]


def test_send_command_does_not_enqueue_an_ack(monkeypatch):
    """El ack del despacho lo construye la strategy, no el controlador."""
    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.send_command("base=90")

    ctrl.stop_reading()
    assert ctrl.read_response() is None  # sólo el sentinel: no hay ack encolado


def test_read_response_blocks_until_data(monkeypatch):
    import threading

    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()

    got: list = []
    t = threading.Thread(target=lambda: got.append(ctrl.read_response()))
    t.start()
    t.join(timeout=0.2)
    assert t.is_alive(), "read_response debe bloquear cuando no hay output"

    String = hooks["String"]
    msg = String()
    msg.data = "base=90"
    hooks["on_data"](msg)          # telemetría pura: no encola respuesta
    msg2 = String()
    msg2.data = "commands=restart"
    hooks["on_data"](msg2)         # esto sí encola

    t.join(timeout=2)
    assert not t.is_alive()
    assert isinstance(got[0], CommandsDescriptionRobotResponse)


def test_stop_reading_unblocks_with_none(monkeypatch):
    _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.stop_reading()
    assert ctrl.read_response() is None


# --- Ros2Strategy ---

def test_strategy_send_publishes_and_acks(monkeypatch):
    published, _ = _install_fake_ros(monkeypatch)
    strat = Ros2Strategy(node_name="n", command_topic="cmd", data_topic="data")

    async def scenario():
        await strat.start()
        await strat.send({
            "jsonrpc": "2.0", "method": "move",
            "params": {"command": "base=90"}, "id": 7,
        })
        msg = await asyncio.wait_for(strat.receive(), 2.0)
        await strat.stop()
        return msg

    msg = asyncio.run(scenario())
    assert published == ["base=90"]
    assert msg["id"] == 7
    assert msg["result"]["status"] == "ok"


def test_strategy_set_telemetry_disable_without_loop():
    strat = Ros2Strategy(node_name="n", command_topic="cmd", data_topic="data")
    assert strat.get_telemetry_enabled() is True
    strat.set_telemetry(False)  # no debe requerir un event loop corriendo
    assert strat.get_telemetry_enabled() is False
