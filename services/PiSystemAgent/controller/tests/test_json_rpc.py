"""Tests del adapter JSON-RPC: despacho y traducción de respuestas."""

import asyncio

import pytest

from controller.json_rpc import (
    JsonRpcCommand,
    JsonRpcNotification,
    JsonRpcResponse,
    dispatch,
    to_jsonrpc,
)
from controller.robot.responses import (
    SENT_ACK,
    CommandsDescriptionRobotResponse,
    DispatchErrorRobotResponse,
    DispatchOkRobotResponse,
    InvalidCommandError,
    RobotCommandRecord,
    RobotResponse,
    StatusRobotResponse,
    StrRobotResponse,
)


class FakeRobot:
    """Doble del controlador: registra lo despachado y puede fallar a pedido."""

    def __init__(self, raises: Exception | None = None):
        self.sent: list[str] = []
        self.sequences: list[list[str]] = []
        self.raises = raises

    def send_command(self, command: str) -> None:
        if self.raises is not None:
            raise self.raises
        self.sent.append(command)

    def execute_sequence(self, commands: list[str]) -> None:
        if self.raises is not None:
            raise self.raises
        self.sequences.append(commands)


def _cmd(**kwargs) -> JsonRpcCommand:
    return JsonRpcCommand.model_validate({"jsonrpc": "2.0", **kwargs})


# --- dispatch ---

def test_dispatch_sends_command_and_returns_ok():
    robot = FakeRobot()
    resp = asyncio.run(dispatch(_cmd(method="move", params={"command": "base=90"}, id=7), robot))

    assert robot.sent == ["base=90"]
    assert isinstance(resp, DispatchOkRobotResponse)
    assert resp.request_id == 7
    assert resp.method == "move"
    assert resp.detail == SENT_ACK


def test_dispatch_falls_back_to_method_as_command():
    robot = FakeRobot()
    asyncio.run(dispatch(_cmd(method="restart", id=1), robot))
    assert robot.sent == ["restart"]


def test_dispatch_preserves_null_id():
    """El WebClient no manda id: debe seguir siendo un DispatchOk, no una notification."""
    resp = asyncio.run(dispatch(_cmd(method="restart"), FakeRobot()))
    assert isinstance(resp, DispatchOkRobotResponse)
    assert resp.request_id is None


def test_dispatch_invalid_command_returns_error():
    robot = FakeRobot(raises=InvalidCommandError("comando desconocido: jump"))
    resp = asyncio.run(dispatch(_cmd(method="jump", id=3), robot))

    assert isinstance(resp, DispatchErrorRobotResponse)
    assert resp.request_id == 3
    assert resp.method == "jump"


def test_dispatch_transport_failure_returns_error():
    robot = FakeRobot(raises=ConnectionError("puerto cerrado"))
    resp = asyncio.run(dispatch(_cmd(method="move", id=4), robot))
    assert isinstance(resp, DispatchErrorRobotResponse)


def test_dispatch_execute_sequence():
    robot = FakeRobot()
    resp = asyncio.run(dispatch(
        _cmd(method="execute_sequence", params={"commands": ["a", "b"]}, id=9), robot
    ))

    assert robot.sequences == [["a", "b"]]
    assert isinstance(resp, DispatchOkRobotResponse)
    assert resp.commands_count == 2
    assert resp.request_id == 9


def test_dispatch_execute_sequence_rejects_non_list():
    resp = asyncio.run(dispatch(
        _cmd(method="execute_sequence", params={"commands": "a,b"}, id=9), FakeRobot()
    ))
    assert isinstance(resp, DispatchErrorRobotResponse)
    assert resp.request_id == 9


def test_dispatch_never_raises_on_unexpected_exception():
    """El invariante es absoluto: un bug del controlador no debe tumbar el agente."""
    robot = FakeRobot(raises=RuntimeError("bug inesperado del controlador"))
    resp = asyncio.run(dispatch(_cmd(method="move", id=5), robot))

    assert isinstance(resp, DispatchErrorRobotResponse)
    assert resp.request_id == 5
    assert to_jsonrpc(resp).error.code == -32603


# --- to_jsonrpc ---

def test_dispatch_ok_becomes_response_with_id():
    msg = to_jsonrpc(DispatchOkRobotResponse(7, "move"))
    assert isinstance(msg, JsonRpcResponse)
    assert msg.id == 7
    assert msg.result is not None
    assert msg.result.status == "ok"
    assert msg.result.method == "move"
    assert msg.result.response == SENT_ACK
    assert msg.error is None


def test_dispatch_ok_without_id_is_still_a_response():
    """La regla es por tipo, no por valor de request_id."""
    msg = to_jsonrpc(DispatchOkRobotResponse(None, "move"))
    assert isinstance(msg, JsonRpcResponse)
    assert msg.id is None
    assert msg.result is not None


def test_dispatch_ok_with_commands_count():
    msg = to_jsonrpc(DispatchOkRobotResponse(1, "execute_sequence", commands_count=3))
    assert isinstance(msg, JsonRpcResponse)
    assert msg.result is not None
    assert msg.result.commands_count == 3


def test_dispatch_error_becomes_error_response_never_a_result():
    msg = to_jsonrpc(DispatchErrorRobotResponse(7, "jump", InvalidCommandError("nope")))
    assert isinstance(msg, JsonRpcResponse)
    assert msg.id == 7
    assert msg.result is None
    assert msg.error is not None
    assert msg.error.message == "nope"


@pytest.mark.parametrize("error,code", [
    (InvalidCommandError("nope"), -32602),
    (ValueError("params"), -32602),
    (ConnectionError("cerrado"), -32603),
    (OSError("io"), -32603),
])
def test_dispatch_error_codes(error, code):
    msg = to_jsonrpc(DispatchErrorRobotResponse(1, "m", error))
    assert isinstance(msg, JsonRpcResponse)
    assert msg.error is not None
    assert msg.error.code == code


def test_str_response_becomes_robot_output_notification():
    msg = to_jsonrpc(StrRobotResponse("OK"))
    assert isinstance(msg, JsonRpcNotification)
    assert msg.method == "robot.output"
    assert msg.params == {"data": "OK"}


def test_commands_description_becomes_command_update_notification():
    msg = to_jsonrpc(CommandsDescriptionRobotResponse(RobotCommandRecord([])))
    assert isinstance(msg, JsonRpcNotification)
    assert msg.method == "command.update"
    assert msg.params == {"commands": []}


def test_status_becomes_status_update_notification():
    msg = to_jsonrpc(StatusRobotResponse({"status": "online"}))
    assert isinstance(msg, JsonRpcNotification)
    assert msg.method == "status.update"
    assert msg.params == {"status": "online"}


def test_unknown_response_type_falls_back_to_robot_output():
    msg = to_jsonrpc(RobotResponse())
    assert isinstance(msg, JsonRpcNotification)
    assert msg.method == "robot.output"
