"""Tests del controlador mock con el contrato nuevo."""

import threading

import pytest

from controller.robot.responses import (
    CommandsDescriptionRobotResponse, InvalidCommandError, StrRobotResponse,
)
from controller.robot.robot_mock_controller import RobotMockController


def test_seeds_command_descriptors_on_connect():
    ctrl = RobotMockController()
    ctrl.connect()
    resp = ctrl.read_response()
    assert isinstance(resp, CommandsDescriptionRobotResponse)
    assert [c["_type"] for c in resp.toList()] == ["toggle", "literal"]


def test_send_command_emits_robot_output():
    ctrl = RobotMockController()
    ctrl.connect()
    _ = ctrl.read_response()  # descarta los descriptores
    ctrl.send_command("start")
    resp = ctrl.read_response()
    assert isinstance(resp, StrRobotResponse)
    assert resp.text == "OK"


def test_send_command_rejects_unknown():
    ctrl = RobotMockController()
    ctrl.connect()
    with pytest.raises(InvalidCommandError):
        ctrl.send_command("jump")


def test_stop_reading_unblocks():
    ctrl = RobotMockController()
    ctrl.connect()
    ctrl.stop_reading()
    _ = ctrl.read_response()  # descriptores
    assert ctrl.read_response() is None


def test_survives_disconnect_reconnect_cycle():
    """Finding 1: connect() debe resetear el estado de lectura.

    disconnect() llama a stop_reading() (idempotente, para poder llamarse standalone
    sin pasar por un stop_reading() explícito previo). Si ya hubo uno antes (el caso
    normal: MockStrategy.stop() llama stop_reading() y LUEGO disconnect()), el `None`
    de disconnect() queda huérfano en la cola. Sin este fix, el próximo connect()
    encola los descriptores DETRÁS de ese huérfano, y el primer read_response() del
    ciclo nuevo devuelve el None viejo en vez de los descriptores — exactamente el
    "canal que parece sano pero está muerto" que este refactor existe para eliminar.
    """
    ctrl = RobotMockController()
    ctrl.connect()
    _ = ctrl.read_response()  # descriptores del primer connect()
    ctrl.stop_reading()  # como haría MockStrategy.stop() antes de los loops
    assert ctrl.read_response() is None
    ctrl.disconnect()  # encola un segundo None, huérfano, si no se resetea la cola

    ctrl.connect()
    resp = ctrl.read_response()
    assert isinstance(resp, CommandsDescriptionRobotResponse), (
        "tras reconectar, read_response() debe entregar los descriptores de nuevo, "
        "no un None residual de la cola del ciclo anterior"
    )

    # Y el canal debe volver a bloquear genuinamente para output nuevo, no estar
    # "drenado" para siempre por basura acumulada.
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
    ctrl.send_command("start")
    assert unblocked.wait(timeout=2.0), "read_response debería desbloquear al llegar output"
    assert isinstance(got[0], StrRobotResponse)
    assert got[0].text == "OK"
