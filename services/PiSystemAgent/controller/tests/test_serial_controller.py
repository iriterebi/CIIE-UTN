"""Tests del controlador serial con un doble de serial.Serial."""

import threading

import pytest

from controller.robot.responses import StrRobotResponse
from controller.robot.robot_controller import RobotController


class FakeSerial:
    """Doble de serial.Serial: readline devuelve b'' al vencer el timeout."""

    def __init__(self, *args, **kwargs):
        self.is_open = True
        self.written: list[bytes] = []
        self._lines: list[bytes] = []
        self._lock = threading.Lock()

    def feed(self, line: str) -> None:
        with self._lock:
            self._lines.append(line.encode("utf-8"))

    def write(self, data: bytes) -> int:
        self.written.append(data)
        return len(data)

    def readline(self) -> bytes:
        with self._lock:
            return self._lines.pop(0) if self._lines else b""

    def close(self) -> None:
        self.is_open = False


@pytest.fixture
def ctrl(monkeypatch):
    fake = FakeSerial()
    monkeypatch.setattr("controller.robot.robot_controller.serial.Serial",
                        lambda *a, **k: fake)
    monkeypatch.setattr("controller.robot.robot_controller.time.sleep", lambda _: None)
    c = RobotController("/dev/fake")
    c.connect()
    return c


def test_read_response_has_no_command_sentinel(ctrl):
    """El #4: antes devolvía StrRobotResponse("", texto) y el "" rompía el ruteo."""
    ctrl.ser.feed("OK")
    resp = ctrl.read_response()
    assert isinstance(resp, StrRobotResponse)
    assert resp.text == "OK"
    assert resp.request_id is None


def test_read_response_skips_timeout_empties(ctrl):
    """readline devuelve b'' al vencer el timeout: no debe salir como respuesta."""
    got: list = []
    t = threading.Thread(target=lambda: got.append(ctrl.read_response()))
    t.start()
    t.join(timeout=0.2)
    assert t.is_alive(), "los vacíos del timeout no deben terminar el read"

    ctrl.ser.feed("OK")
    t.join(timeout=2)
    assert not t.is_alive()
    assert got[0].text == "OK"


def test_stop_reading_unblocks(ctrl):
    got: list = []
    t = threading.Thread(target=lambda: got.append(ctrl.read_response()))
    t.start()
    ctrl.stop_reading()
    t.join(timeout=2)
    assert not t.is_alive()
    assert got[0] is None


def test_execute_sequence_does_not_read(ctrl):
    """Antes leía por cada comando y le robaba respuestas al loop."""
    ctrl.execute_sequence(["a", "", "b"])
    assert ctrl.ser.written == [b"a\n", b"b\n"]


def test_survives_disconnect_reconnect_cycle(monkeypatch):
    """Finding 1: connect() debe limpiar self._stop.

    Sin esto, el Event que setea stop_reading() queda en True para siempre: tras el
    primer disconnect(), un connect() posterior sobre la misma instancia no alcanza
    a resetearlo, y read_response() devuelve None de inmediato en cada llamada
    siguiente — el canal "parece" reconectado (status online) pero está muerto.

    No reutiliza el fixture `ctrl`: su doble (`lambda *a, **k: fake`) retorna siempre
    LA MISMA instancia de FakeSerial, así que tras un close() real quedaría con
    `is_open=False` para siempre — eso ocultaría el bug bajo otro, distinto. Un
    `serial.Serial(...)` real abre un puerto nuevo en cada connect(); esta fábrica
    imita eso.
    """
    monkeypatch.setattr("controller.robot.robot_controller.serial.Serial",
                        lambda *a, **k: FakeSerial())
    monkeypatch.setattr("controller.robot.robot_controller.time.sleep", lambda _: None)
    c = RobotController("/dev/fake")
    c.connect()
    c.stop_reading()
    assert c.read_response() is None
    c.disconnect()

    c.connect()
    got: list = []
    unblocked = threading.Event()

    def reader():
        got.append(c.read_response())
        unblocked.set()

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    assert not unblocked.wait(timeout=0.2), (
        "read_response debería bloquear tras reconectar, no devolver None de inmediato "
        "(self._stop quedó en True de un ciclo anterior)"
    )
    c.ser.feed("OK")
    assert unblocked.wait(timeout=2.0), "read_response debería desbloquear al llegar data"
    assert got[0].text == "OK"
