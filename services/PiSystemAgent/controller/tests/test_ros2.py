"""Tests del controlador/strategy ROS 2.

No requieren ROS 2 instalado: `conftest.py` registra stubs para poder importar los
módulos, y cada test reemplaza `Node`/`String`/`rclpy` en `ros2_controller` con
fakes vía `monkeypatch`. El executor se inyecta (`rclExecutor`) como un fake que
registra los nodos agregados/quitados.
"""

import asyncio
import logging
import types

import pytest

from ..robot import ros2_controller
from ..robot.responses import (
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
)
from ..robot.ros2_controller import Ros2Controller, parse_key_value
from ..strategy.local.ros2_strategy import Ros2Strategy

# --- Fakes de rclpy / std_msgs ---


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
    """Reemplaza Node/String/rclpy en `ros2_controller`. Devuelve (published, hooks)."""
    published: list[str] = []
    hooks: dict[str, object] = {}

    class String:
        def __init__(self):
            self.data = ""

    class FakePublisher:
        def publish(self, msg):
            published.append(msg.data)

    class FakeNode:
        def __init__(self, name):
            self.name = name
            self.context = types.SimpleNamespace(get_domain_id=lambda: 42)

        def create_publisher(self, msg_type, topic, depth):
            return FakePublisher()

        def create_subscription(self, msg_type, topic, callback, depth):
            hooks["on_data"] = callback
            return object()

        def destroy_node(self):
            hooks["destroyed"] = True

    fake_rclpy = types.SimpleNamespace(
        ok=lambda: True,
        shutdown=lambda *a, **k: hooks.__setitem__("shutdown", True),
    )

    monkeypatch.setattr(ros2_controller, "rclpy", fake_rclpy)
    monkeypatch.setattr(ros2_controller, "Node", FakeNode)
    monkeypatch.setattr(ros2_controller, "String", String)

    hooks["String"] = String
    return published, hooks


def _controller(executor=None):
    return Ros2Controller(
        node_name="test_node",
        command_topic="cmd",
        data_topic="data",
        rclExecutor=executor if executor is not None else _FakeExecutor(),
    )


def _strategy():
    return Ros2Strategy(
        node_name="n", command_topic="cmd", data_topic="data", rclExecutor=_FakeExecutor(),
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

def test_connect_adds_node_to_shared_executor(monkeypatch):
    _install_fake_ros(monkeypatch)
    executor = _FakeExecutor()
    ctrl = _controller(executor)
    ctrl.connect()
    assert [n.name for n in executor.nodes] == ["test_node"]


def test_connect_logs_domain_id_from_rclpy_context(monkeypatch, caplog):
    """El dominio lo fija rclpy.init(domain_id=...): hay que leerlo del contexto,
    no de la variable de entorno ROS_DOMAIN_ID (que puede no existir)."""
    monkeypatch.delenv("ROS_DOMAIN_ID", raising=False)
    _install_fake_ros(monkeypatch)
    ctrl = _controller()
    caplog.set_level(logging.INFO)
    ctrl.connect()
    assert "domain=42" in caplog.text


def test_disconnect_removes_node_without_shutting_down_rclpy(monkeypatch):
    """El contexto rclpy es de toda la app: detener la strategy no debe matarlo
    (si no, también moriría el nodo de la cámara, que comparte el contexto)."""
    _, hooks = _install_fake_ros(monkeypatch)
    executor = _FakeExecutor()
    ctrl = _controller(executor)
    ctrl.connect()
    ctrl.disconnect()
    assert executor.nodes == []
    assert hooks.get("destroyed") is True
    assert "shutdown" not in hooks


def test_send_command_publishes(monkeypatch):
    published, _ = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.send_command("base=90")
    assert published == ["base=90"]


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


def test_telemetry_snapshot_is_not_mutated_by_later_data(monkeypatch):
    """`get()` entrega una referencia que el lector usa fuera del lock (get_status la
    copia después): la telemetría nueva debe reemplazar el dict, no modificarlo."""
    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    String = hooks["String"]

    msg = String()
    msg.data = "base=90"
    hooks["on_data"](msg)
    snapshot = ctrl._latest_status.get()

    msg2 = String()
    msg2.data = "mano=10"
    hooks["on_data"](msg2)

    assert snapshot == {"base": "90"}
    assert ctrl.get_status()["telemetry"] == {"base": "90", "mano": "10"}


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


def test_survives_disconnect_reconnect_cycle(monkeypatch):
    """Finding 1: connect() debe resetear la cola de respuestas.

    disconnect() llama a stop_reading() (idempotente — standalone debe poder
    llamarse sin un stop_reading() explícito previo). Si ya hubo uno antes (el caso
    normal: Ros2Strategy.stop() llama stop_reading() y LUEGO disconnect()), el
    `None` de disconnect() queda huérfano en la cola. Sin este fix, el próximo
    connect() no tiene forma de limpiarlo, y el primer read_response() del ciclo
    nuevo devuelve ese None huérfano en vez de la telemetría real que llega después
    — el mismo "canal que parece sano pero está muerto" de Finding 1 en los otros
    dos controladores.
    """
    import threading

    _, hooks = _install_fake_ros(monkeypatch)
    ctrl = _controller()
    ctrl.connect()
    ctrl.stop_reading()  # como haría Ros2Strategy.stop() antes de los loops
    assert ctrl.read_response() is None
    ctrl.disconnect()  # encola un segundo None, huérfano, si no se resetea la cola

    ctrl.connect()
    got: list = []
    unblocked = threading.Event()

    def reader():
        got.append(ctrl.read_response())
        unblocked.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    assert not unblocked.wait(timeout=0.2), (
        "read_response no debería desbloquear sin que llegue output nuevo"
    )

    String = hooks["String"]
    msg = String()
    msg.data = "commands=restart"
    hooks["on_data"](msg)

    assert unblocked.wait(timeout=2.0), "read_response debería desbloquear al llegar data"
    assert isinstance(got[0], CommandsDescriptionRobotResponse)


# --- Ros2Strategy ---

def test_strategy_send_publishes_and_acks(monkeypatch):
    published, _ = _install_fake_ros(monkeypatch)
    strat = _strategy()

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
    strat = _strategy()
    assert strat.get_telemetry_enabled() is True
    strat.set_telemetry(False)  # no debe requerir un event loop corriendo
    assert strat.get_telemetry_enabled() is False
