"""Tests de OutboxLocalStrategy contra un robot falso."""

import asyncio
import queue
from typing import Any, override

import pytest

from controller.robot.responses import (
    SENT_ACK,
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
    RobotCommandRecord,
    RobotResponse,
    StrRobotResponse,
)
from controller.strategy.base import OutboxLocalStrategy, State


class FakeRobot:
    """Robot falso con el contrato nuevo: send levanta, read bloquea, stop desbloquea."""

    def __init__(self):
        self._q: queue.Queue[RobotResponse | None] = queue.Queue()
        self.sent: list[str] = []
        self.valid_commands: set[str] | None = None

    def emit(self, resp: RobotResponse) -> None:
        """Simula output espontáneo del robot."""
        self._q.put(resp)

    def send_command(self, command: str) -> None:
        if self.valid_commands is not None and command not in self.valid_commands:
            raise InvalidCommandError(f"comando desconocido: {command}")
        self.sent.append(command)

    def execute_sequence(self, commands: list[str]) -> None:
        for c in commands:
            self.send_command(c)

    def read_response(self) -> RobotResponse | None:
        return self._q.get()

    def stop_reading(self) -> None:
        self._q.put(None)

    def get_status(self) -> dict[str, Any]:
        return {"status": "online", "mock": True}


class FakeStrategy(OutboxLocalStrategy):
    def __init__(self):
        super().__init__()
        self._robot: FakeRobot = FakeRobot()

    @override
    async def start(self) -> None:
        self._start_loops()
        self._state = State.RUNNING

    @override
    async def stop(self) -> None:
        self._robot.stop_reading()
        await self._stop_loops()
        self._state = State.STOPPED


async def _drain(strat: FakeStrategy, n: int, timeout: float = 2.0):
    return [await asyncio.wait_for(strat.receive(), timeout) for _ in range(n)]


def test_send_emits_dispatch_response_with_id():
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        await strat.send({"jsonrpc": "2.0", "method": "move",
                          "params": {"command": "base=90"}, "id": 7})
        msg = await asyncio.wait_for(strat.receive(), 2.0)
        await strat.stop()
        return strat, msg

    strat, msg = asyncio.run(scenario())
    assert strat._robot.sent == ["base=90"]
    assert msg["id"] == 7
    assert msg["result"]["status"] == "ok"
    assert msg["result"]["response"] == SENT_ACK


def test_send_invalid_command_emits_error_with_id():
    async def scenario():
        strat = FakeStrategy()
        strat._robot.valid_commands = {"start"}
        await strat.start()
        await strat.send({"jsonrpc": "2.0", "method": "jump", "id": 3})
        msg = await asyncio.wait_for(strat.receive(), 2.0)
        await strat.stop()
        return msg

    msg = asyncio.run(scenario())
    assert msg["id"] == 3
    assert msg["result"] is None
    assert msg["error"]["code"] == -32602


def test_response_loop_drains_without_any_command():
    """El #7: el output del robot sale aunque nadie mande comandos."""
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        for i in range(5):
            strat._robot.emit(StrRobotResponse(f"linea-{i}"))
        msgs = await _drain(strat, 5)
        await strat.stop()
        return msgs

    msgs = asyncio.run(scenario())
    assert [m["params"]["data"] for m in msgs] == [f"linea-{i}" for i in range(5)]
    assert all(m["method"] == "robot.output" for m in msgs)
    assert all("id" not in m for m in msgs)


def test_command_descriptors_arrive_as_notifications():
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        strat._robot.emit(CommandsDescriptionRobotResponse(RobotCommandRecord([])))
        msg = await asyncio.wait_for(strat.receive(), 2.0)
        await strat.stop()
        return msg

    msg = asyncio.run(scenario())
    assert msg["method"] == "command.update"


def test_stop_terminates_the_response_loop():
    """stop() no debe retornar con el loop todavía vivo."""
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        task = strat._response_task
        await asyncio.wait_for(strat.stop(), 2.0)
        return task

    task = asyncio.run(scenario())
    assert task is not None and task.done()
    assert strat_state_cleared(task)


def strat_state_cleared(task) -> bool:
    """La tarea terminó, por cancelación o por el sentinel: ambas son fin limpio."""
    return task.cancelled() or task.exception() is None


def test_set_telemetry_toggles_without_running_loop():
    strat = FakeStrategy()
    assert strat.get_telemetry_enabled() is True
    strat.set_telemetry(False)
    assert strat.get_telemetry_enabled() is False
