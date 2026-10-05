"""Tests de OutboxLocalStrategy contra un robot falso."""

import asyncio
import queue
import threading
from typing import Any, override

import pytest

import controller.strategy.base as base_module
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
        # Se marca DESPUÉS de que el `queue.Queue.get()` bloqueante realmente
        # retorna, en el hilo real del executor. Distingue "el Task dice done()"
        # (que puede pasar solo por cancelación, sin que el hilo real se mueva)
        # de "el hilo real efectivamente se desbloqueó" — ver finding 1.
        self.read_thread_returned = threading.Event()

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
        result = self._q.get()
        self.read_thread_returned.set()
        return result

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
    """stop() no debe retornar con el loop todavía vivo.

    No alcanza con mirar `task.done()`: `_response_loop` atrapa `CancelledError`
    adentro, así que el Task se reporta "terminado" apenas se cancela, aunque el
    hilo REAL bloqueado en `read_response` todavía no haya retornado (el cancel
    del lado asyncio se desacopla del `concurrent.futures.Future` subyacente una
    vez que el hilo ya está corriendo — ver finding 1 / investigación empírica).

    Tampoco alcanza un snapshot instantáneo de `read_thread_returned.is_set()`
    apenas `stop()` retorna: eso resultó ser OTRA carrera (contra el scheduler
    del hilo real), que puede fallar incluso con la implementación correcta.
    Por eso se usa `Event.wait(timeout=...)`: cota superior determinística que
    pasa rápido cuando el sentinel ya se mandó, y SIEMPRE agota el timeout (sin
    azar) si `stop_reading()` nunca se llamó — ver fix report para la evidencia
    negativa de ambos casos.
    """
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        await asyncio.sleep(0.05)  # dejar que el loop entre genuinamente al read bloqueante
        strat._robot.read_thread_returned.clear()
        task = strat._response_task
        await asyncio.wait_for(strat.stop(), 2.0)
        return strat, task

    strat, task = asyncio.run(scenario())
    assert task is not None and task.done()
    assert strat_state_cleared(task)
    assert strat._robot.read_thread_returned.wait(timeout=1.0), (
        "el hilo real de read_response nunca retornó: stop() no esperó al sentinel "
        "(cota de 1s agotada, no es una carrera instantánea)"
    )


def strat_state_cleared(task) -> bool:
    """La tarea terminó, por cancelación o por el sentinel: ambas son fin limpio."""
    return task.cancelled() or task.exception() is None


def test_response_loop_death_sets_state_stopped():
    """Finding 2: si el canal de output del robot muere (error de E/S), el
    strategy debe quedar observable como detenido. `send()` sigue funcionando
    porque `dispatch()` es independiente, así que sin esto el strategy parecería
    vivo mientras descarta todo output espontáneo del robot para siempre."""
    async def scenario():
        strat = FakeStrategy()

        def _raise() -> RobotResponse | None:
            raise ConnectionError("serial desconectado")

        strat._robot.read_response = _raise
        await strat.start()
        await asyncio.wait_for(strat._response_task, 2.0)  # el loop muere solo
        status_after_death = strat.status
        await strat.stop()
        return status_after_death

    status_after_death = asyncio.run(scenario())
    assert status_after_death == State.STOPPED


def test_stop_completes_cleanly_after_telemetry_loop_dies(monkeypatch: pytest.MonkeyPatch):
    """Finding 3: si `get_status()` falla, el telemetry loop muere solo con una
    excepción pendiente en su Task. Antes de este fix, `_stop_loops()` la
    re-lanzaba al awaitear esa tarea, y `stop()` rompía su contrato de shutdown
    determinista. Acá no debe pasar: perder telemetría es degradación, no
    motivo para que el strategy entero falle al apagarse."""
    monkeypatch.setattr(base_module, "STATUS_INTERVAL_SEC", 0.01)

    async def scenario():
        strat = FakeStrategy()

        def _raise() -> dict[str, Any]:
            raise ConnectionError("telemetría caída")

        strat._robot.get_status = _raise
        await strat.start()
        telemetry_task = strat._telemetry_task
        assert telemetry_task is not None
        await asyncio.wait_for(telemetry_task, 2.0)  # el loop muere solo, antes de stop()
        await asyncio.wait_for(strat.stop(), 2.0)  # no debe relanzar la excepción
        return strat, telemetry_task

    strat, telemetry_task = asyncio.run(scenario())
    assert telemetry_task.done() and telemetry_task.exception() is None
    assert strat.status == State.STOPPED


def test_set_telemetry_disable_needs_no_running_loop():
    """`set_telemetry(False)` no crea una tarea (solo cancela una existente, y
    acá no hay ninguna todavía), así que no necesita un event loop corriendo.
    No cubre el camino `enabled=True` — ver el test siguiente."""
    strat = FakeStrategy()
    assert strat.get_telemetry_enabled() is True
    strat.set_telemetry(False)
    assert strat.get_telemetry_enabled() is False


def test_set_telemetry_enable_creates_task_in_async_context():
    """El camino `enabled=True` sí necesita loop corriendo (hace
    `asyncio.create_task`); en producción los llamadores (`MicroCore._handle_switch`,
    `pause`/`resume`) siempre están en contexto async, así que no hace falta
    blindarlo para el caso síncrono (YAGNI)."""
    async def scenario():
        strat = FakeStrategy()
        strat.set_telemetry(False)
        assert strat.get_telemetry_enabled() is False
        assert strat._telemetry_task is None

        strat.set_telemetry(True)
        assert strat.get_telemetry_enabled() is True
        task = strat._telemetry_task
        assert task is not None and not task.done()

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())
