"""Tests de OutboxLocalStrategy contra un robot falso."""

import asyncio
import queue
import threading
import time
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
    """Usa la plantilla start/stop/pause/resume de OutboxLocalStrategy sin cambios:
    estos tests ejercitan esa plantilla, no una reimplementación paralela de ella.
    FakeRobot no modela conexión, así que los hooks son no-ops."""

    def __init__(self):
        super().__init__()
        self._robot: FakeRobot = FakeRobot()

    @override
    async def _connect_robot(self) -> None:
        pass

    @override
    async def _disconnect_robot(self) -> None:
        pass


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


def test_send_malformed_message_is_dropped_not_raised():
    """Fix 3 (harden `send()`): un frame que no valida contra `JsonRpcCommand`
    (ej. lo que produciría un `_parse_message` de `WsStrategy` sin este fix, o
    cualquier otro frame malformado) debe descartarse con un log, nunca escapar
    como `ValidationError` hacia el `TaskGroup` de `MicroCore` — mismo invariante
    "nunca levanta" que `dispatch()`."""
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        await strat.send({"no_es_un_comando": True})  # falta 'method' -> inválido
        # Un comando válido posterior debe seguir funcionando: send() no debe
        # haber quedado en un estado roto por el frame descartado.
        await strat.send({"jsonrpc": "2.0", "method": "start", "id": 1})
        msg = await asyncio.wait_for(strat.receive(), 2.0)
        await strat.stop()
        return strat, msg

    strat, msg = asyncio.run(scenario())
    assert strat._outbox.empty()  # el frame malformado no encoló nada
    assert msg["id"] == 1
    assert msg["result"]["status"] == "ok"


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


def test_disconnect_never_runs_before_the_real_read_thread_returns():
    """Fix 2: `_disconnect_robot()` no debe correr mientras el hilo real sigue
    bloqueado en `read_response`. `FakeRobot.read_response` (vía `queue.get()`)
    es casi instantáneo, así que no expone la carrera por timing — este test usa
    un robot con una lectura deliberadamente lenta (como el timeout=1 real del
    puerto serial) para forzar la ventana donde, antes del fix, `task.cancel()`
    ganaba la carrera contra el sentinel y `_stop_loops()` retornaba con el hilo
    todavía vivo."""
    class SlowFakeRobot(FakeRobot):
        def read_response(self):
            time.sleep(0.3)
            return super().read_response()

    class SlowFakeStrategy(FakeStrategy):
        def __init__(self):
            super().__init__()
            self._robot: SlowFakeRobot = SlowFakeRobot()
            self.disconnect_saw_thread_returned: bool | None = None

        @override
        async def _disconnect_robot(self) -> None:
            self.disconnect_saw_thread_returned = self._robot.read_thread_returned.is_set()

    async def scenario():
        strat = SlowFakeStrategy()
        await strat.start()
        await asyncio.sleep(0.05)  # dejar que el loop entre genuinamente al read bloqueante
        strat._robot.read_thread_returned.clear()
        await asyncio.wait_for(strat.stop(), 2.0)
        return strat

    strat = asyncio.run(scenario())
    assert strat.disconnect_saw_thread_returned is True, (
        "_disconnect_robot() corrió mientras el hilo real de read_response todavía "
        "estaba bloqueado -- la precondición que _stop_loops() debe garantizar"
    )


@pytest.mark.parametrize("exc_cls", [ConnectionError, RuntimeError])
def test_response_loop_death_sets_state_stopped(exc_cls: type[Exception]):
    """Finding 2: si el canal de output del robot muere (cualquier error, no sólo
    E/S), el strategy debe quedar observable como detenido. `send()` sigue
    funcionando porque `dispatch()` es independiente, así que sin esto el
    strategy parecería vivo mientras descarta todo output espontáneo del robot
    para siempre.

    Parametrizado sobre `RuntimeError` además de `ConnectionError`: antes del fix
    1, el loop sólo atrapaba `(ConnectionError, OSError)`, así que este test
    pasaba con el bug presente (sólo ejercitaba una causa que YA estaba
    cubierta). El disparador original fue un `UnicodeDecodeError` (hereda de
    `ValueError`) en el controlador serial, ya eliminado; `RuntimeError` alcanza para probar
    que el `except` es genérico sin acoplarse a una jerarquía de excepciones
    puntual.
    """
    async def scenario():
        strat = FakeStrategy()

        def _raise() -> RobotResponse | None:
            raise exc_cls("serial desconectado")

        strat._robot.read_response = _raise
        await strat.start()
        await asyncio.wait_for(strat._response_task, 2.0)  # el loop muere solo
        status_after_death = strat.status
        await strat.stop()
        return status_after_death

    status_after_death = asyncio.run(scenario())
    assert status_after_death == State.STOPPED


@pytest.mark.parametrize("exc_cls", [ConnectionError, RuntimeError])
def test_stop_completes_cleanly_after_telemetry_loop_dies(
    monkeypatch: pytest.MonkeyPatch, exc_cls: type[Exception]
):
    """Finding 3: si `get_status()` falla, el telemetry loop muere solo con una
    excepción pendiente en su Task. Antes de este fix, `_stop_loops()` la
    re-lanzaba al awaitear esa tarea, y `stop()` rompía su contrato de shutdown
    determinista. Acá no debe pasar: perder telemetría es degradación, no
    motivo para que el strategy entero falle al apagarse.

    Parametrizado igual que `test_response_loop_death_sets_state_stopped` (ver
    ahí el porqué de `RuntimeError`): con sólo `ConnectionError` este test pasaba
    con el bug presente, porque esa causa ya estaba en el `except` original.

    También fija Fix 5: la asimetría respuesta/telemetría respecto a `_state` es
    deliberada (perder telemetría es degradación, no muerte del strategy) — acá
    se pin-ea con un assert explícito para que una futura "unificación" no la
    rompa en silencio.
    """
    monkeypatch.setattr(base_module, "STATUS_INTERVAL_SEC", 0.01)

    async def scenario():
        strat = FakeStrategy()

        def _raise() -> dict[str, Any]:
            raise exc_cls("telemetría caída")

        strat._robot.get_status = _raise
        await strat.start()
        telemetry_task = strat._telemetry_task
        assert telemetry_task is not None
        await asyncio.wait_for(telemetry_task, 2.0)  # el loop muere solo, antes de stop()
        status_right_after_telemetry_death = strat.status
        await asyncio.wait_for(strat.stop(), 2.0)  # no debe relanzar la excepción
        return strat, telemetry_task, status_right_after_telemetry_death

    strat, telemetry_task, status_right_after_telemetry_death = asyncio.run(scenario())
    assert telemetry_task.done() and telemetry_task.exception() is None
    # Fix 5: la muerte del telemetry loop NO debe tocar `_state` — a diferencia
    # de la muerte del response loop, es degradación, no caída del strategy.
    assert status_right_after_telemetry_death != State.STOPPED
    assert strat.status == State.STOPPED  # stop() sí lo deja detenido, al final


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
