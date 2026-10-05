"""Tests del controlador mock con el contrato nuevo."""

import pytest

from controller.robot.responses import (
    CommandsDescriptionRobotResponse, InvalidCommandError, StrRobotResponse,
)
from controller.robot.robot_mock_controller import RobotMockController


def test_seeds_command_descriptors_on_connect():
    ctrl = RobotMockController("/dev/null")
    ctrl.connect()
    resp = ctrl.read_response()
    assert isinstance(resp, CommandsDescriptionRobotResponse)
    assert [c["_type"] for c in resp.toList()] == ["toggle", "literal"]


def test_send_command_emits_robot_output():
    ctrl = RobotMockController("/dev/null")
    ctrl.connect()
    _ = ctrl.read_response()  # descarta los descriptores
    ctrl.send_command("start")
    resp = ctrl.read_response()
    assert isinstance(resp, StrRobotResponse)
    assert resp.text == "OK"


def test_send_command_rejects_unknown():
    ctrl = RobotMockController("/dev/null")
    ctrl.connect()
    with pytest.raises(InvalidCommandError):
        ctrl.send_command("jump")


def test_stop_reading_unblocks():
    ctrl = RobotMockController("/dev/null")
    ctrl.connect()
    ctrl.stop_reading()
    _ = ctrl.read_response()  # descriptores
    assert ctrl.read_response() is None
