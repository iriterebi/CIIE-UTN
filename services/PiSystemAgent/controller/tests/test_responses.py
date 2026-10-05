"""Tests del vocabulario de dominio: descriptores de comandos y respuestas."""

import json

import pytest

from controller.robot.responses import (
    SENT_ACK,
    CommandsDescriptionRobotResponse,
    DispatchErrorRobotResponse,
    DispatchOkRobotResponse,
    InvalidCommandError,
    LiteralRobotCommand,
    RobotCommandRecord,
    RobotResponse,
    StatusRobotResponse,
    StrRobotResponse,
    ToggleRobotCommand,
    TypedRobotCommand,
    parse_commands,
)


# --- Descriptores ---

def test_parse_commands_literal_and_toggle_and_typed():
    record = parse_commands("commands=restart,<toggle:start|stop>play,<type:uint>speed")
    assert [type(c) for c in record.commands] == [
        LiteralRobotCommand, ToggleRobotCommand, TypedRobotCommand,
    ]


@pytest.mark.parametrize("descriptor", [
    "<toggle:start>play",       # falta el segundo literal
    "<toggle:start|>play",      # segundo literal vacío
    "<toggle:|stop>play",       # primer literal vacío
    "<toggle:a|b|c>play",       # tres literales
])
def test_parse_commands_skips_malformed_toggle(descriptor):
    record = parse_commands(f"commands={descriptor},restart")
    assert [c.command for c in record.commands] == ["restart"]


def test_toggle_todict_is_json_serializable():
    record = RobotCommandRecord([ToggleRobotCommand("play", "start", "stop")])
    payload = CommandsDescriptionRobotResponse(record).toList()

    assert json.loads(json.dumps(payload)) == [{
        "_type": "toggle",
        "mets_name": "play",
        "true": {"_type": "literal", "command": "start"},
        "false": {"_type": "literal", "command": "stop"},
    }]


@pytest.mark.parametrize("command,expected", [
    ("10", True), (10, True), ("0", True),
    ("-1", False), (-1, False),
    ("abc", False), ("", False), ("1.5", False),
    (True, False),
])
def test_typed_uint_valid(command, expected):
    assert TypedRobotCommand("speed", "uint").valid(command) is expected


def test_record_valid_fails_open_before_discovery():
    assert RobotCommandRecord([]).valid("lo_que_sea") is True


def test_record_valid_rejects_unknown_once_discovered():
    record = parse_commands("commands=restart,<toggle:start|stop>play")
    assert record.valid("start") is True
    assert record.valid("restart") is True
    assert record.valid("jump") is False


# --- Respuestas ---

def test_robot_response_has_no_request_id_by_default():
    assert RobotResponse().request_id is None
    assert StrRobotResponse("OK").request_id is None
    assert StatusRobotResponse({"a": 1}).request_id is None
    assert CommandsDescriptionRobotResponse(RobotCommandRecord([])).request_id is None


def test_dispatch_responses_carry_request_id():
    assert DispatchOkRobotResponse(7, "move").request_id == 7
    assert DispatchErrorRobotResponse(7, "move", ValueError("x")).request_id == 7


def test_dispatch_ok_defaults_to_sent_ack():
    ok = DispatchOkRobotResponse(1, "move")
    assert ok.detail == SENT_ACK
    assert ok.commands_count is None


def test_dispatch_ok_carries_commands_count():
    assert DispatchOkRobotResponse(1, "execute_sequence", commands_count=3).commands_count == 3


def test_str_responses_stringify():
    assert str(StrRobotResponse("OK")) == "OK"
    assert str(DispatchErrorRobotResponse(1, "move", ValueError("roto"))) == "roto"


def test_base_response_str_does_not_crash():
    """La base vieja tenía `def __str__(self) -> str: ...` y devolvía None."""
    assert isinstance(str(StatusRobotResponse({})), str)
    assert isinstance(str(CommandsDescriptionRobotResponse(RobotCommandRecord([]))), str)


def test_invalid_command_error_is_a_value_error():
    assert issubclass(InvalidCommandError, ValueError)
