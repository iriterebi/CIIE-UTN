# Desacople de despacho y respuestas — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar el envío de un comando del envío de las respuestas del robot, de modo que el `id` de JSON-RPC deje de perderse, la ruta serial deje de usar `""` como centinela y la lista de respuestas deje de crecer sin tope.

**Architecture:** Tres productores (el despacho, un loop que lee del robot, un loop de telemetría) escriben objetos `RobotResponse` polimórficos en una única cola por strategy local. Un solo consumidor (`receive()`) los traduce a JSON-RPC. El tipo del `RobotResponse` decide si sale como respuesta correlacionada o como notification.

**Tech Stack:** Python 3.12+ (el contenedor de deploy trae 3.12; el venv de dev es 3.13), pydantic v2, asyncio, `queue.Queue` para el cruce thread↔asyncio, pytest.

**Spec:** `docs/superpowers/specs/2026-10-05-desacople-dispatch-respuestas-design.md`

## Global Constraints

- **Todo el código vive bajo `services/PiSystemAgent/`.** Ningún archivo fuera de ese directorio se toca. El WebClient está explícitamente fuera de alcance.
- **Documentación y comentarios en español.** Convención del repo.
- **Correr los tests con `sys.argv` limpio.** `controller/config.py:107` instancia `Config()` a nivel de módulo con `cli_parse_args=True`, así que importar cualquier cosa bajo `controller.robot` parsea `sys.argv` y pytest muere con `SystemExit: 2` ante cualquier flag. Hasta que se arregle el hallazgo #10, el comando de test es:

  ```bash
  cd services/PiSystemAgent && uv run python -c "
  import sys, pytest
  sys.argv = ['pytest']
  sys.exit(pytest.main(['-q', 'controller/tests/<archivo>']))
  "
  ```

  Pasar el archivo concreto también esquiva el hallazgo #9 (`controller/tests/test_video_ws_client.py` aborta la colección completa por falta de `__init__.py`).
- **El modo demo debe seguir funcionando sin hardware** (`MOCK_ROBOT=1`). Es criterio de aceptación, no un extra.
- **No tocar `ros_tryouts/`** ni `services/PiRobotDriver/`.
- **Nombres del contrato del controlador, idénticos en los tres:** `send_command(command: str) -> None`, `read_response() -> RobotResponse | None`, `stop_reading() -> None`, `execute_sequence(commands: list[str]) -> None`, `get_status() -> dict[str, Any]`, `connect()`, `disconnect()`.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `controller/robot/responses.py` **(nuevo)** | Vocabulario de dominio: árbol `RobotResponse`, árbol `RobotCommand`, `parse_commands`, `InvalidCommandError`. Lo comparten los tres controladores y el adapter. |
| `controller/robot/ros2_controller.py` | Sólo el nodo rclpy. Pierde los dos árboles de tipos. |
| `controller/robot/robot_controller.py` | Sólo serial. |
| `controller/robot/robot_mock_controller.py` | Sólo mock. |
| `controller/json_rpc.py` | Adapter JSON-RPC: modelos pydantic + `dispatch()` + `to_jsonrpc()`. |
| `controller/strategy/base.py` | `Strategy`, `LocalStrategy` y la nueva `OutboxLocalStrategy` (cola + los dos loops + `send`/`receive`). |
| `controller/strategy/local/*.py` | Sólo construcción del controlador y `start`/`stop`. |
| `controller/tests/test_responses.py` **(nuevo)** | Árbol de tipos y parsing de descriptores. |
| `controller/tests/test_json_rpc.py` **(nuevo)** | `dispatch()` y `to_jsonrpc()`. |
| `controller/tests/test_outbox_strategy.py` **(nuevo)** | `OutboxLocalStrategy` contra un robot falso. |
| `controller/tests/test_ros2.py` | Sólo lo específico del controlador ROS 2. |

**Orden y estado del árbol:** las tareas 1-3 agregan código nuevo que nadie usa todavía, así que el árbol queda verde después de cada una. La tarea 4 es el *flip*: cambia el contrato de los tres controladores y rehace las tres strategies de una vez. No se puede hacer incremental — `handle_json_rpc` es compartido por las tres strategies, así que cualquier cambio al contrato las rompe a las tres simultáneamente (ver Riesgo 1 del spec). Dentro de la tarea 4 el árbol está rojo entre el paso 3 y el paso 14.

---

### Task 1: Módulo `responses.py`

Extrae los dos árboles de tipos fuera de `ros2_controller.py` y les aplica la semántica nueva. Nadie lo importa todavía: `ros2_controller.py` conserva su copia hasta la tarea 4.

**Files:**
- Create: `services/PiSystemAgent/controller/robot/responses.py`
- Create: `services/PiSystemAgent/controller/tests/test_responses.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `SENT_ACK: str`
  - `InvalidCommandError(ValueError)`
  - `RobotCommand`, `LiteralRobotCommand(command)`, `ToggleRobotCommand(command_name, command_true, command_false)`, `TypedRobotCommand(command_name, type_descriptor)`, `RobotCommandRecord(commands: list[RobotCommand])`, `parse_commands(serialiced: str) -> RobotCommandRecord`
  - `RobotResponse(request_id: str | int | None = None)`
  - `StrRobotResponse(text: str)` — atributo `.text`
  - `CommandsDescriptionRobotResponse(commands: RobotCommandRecord)` — método `.toList()`
  - `StatusRobotResponse(status: dict[str, Any])` — atributo `.status`
  - `DispatchOkRobotResponse(request_id, method: str, detail: str = SENT_ACK, commands_count: int | None = None)`
  - `DispatchErrorRobotResponse(request_id, method: str, error: Exception)` — atributo `.error`

- [ ] **Step 1: Escribir el test que falla**

Crear `controller/tests/test_responses.py`:

```python
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
```

- [ ] **Step 2: Correr el test y verificar que falla**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_responses.py']))
"
```

Esperado: error de colección, `ModuleNotFoundError: No module named 'controller.robot.responses'`.

- [ ] **Step 3: Crear `responses.py` — mitad descriptores**

Crear `controller/robot/responses.py` con este encabezado:

```python
"""Vocabulario de dominio del robot: descriptores de comandos y respuestas.

Vive aparte de los controladores porque los tres (`ros2_controller`,
`robot_controller`, `robot_mock_controller`) y el adapter `json_rpc` lo comparten.
Antes estaba dentro de `ros2_controller.py`, lo que acoplaba el mock y el serial al
módulo de ROS 2.

Regla de correlación: el TIPO decide el sobre JSON-RPC.
`DispatchOkRobotResponse`/`DispatchErrorRobotResponse` son el resultado de despachar
un comando del usuario y llevan `request_id`; todo lo demás es output espontáneo del
robot y sale como notification.
"""

import logging
import re
from typing import Any, Final, override

logger = logging.getLogger(__name__)

# Payload por defecto del ack de despacho. Ni el Arduino ni el agente ROS 2 confirman
# ejecución, así que lo único afirmable es que el comando salió.
SENT_ACK = "mensaje enviado"


class InvalidCommandError(ValueError):
    """El comando no matchea ningún descriptor publicado por el robot."""
```

Después, **mover verbatim** desde `controller/robot/ros2_controller.py` las líneas **34-176** (de `class RobotCommand:` hasta `return RobotCommandRecord(commands)` inclusive). Ese bloque ya está correcto y no se modifica: cubre `RobotCommand`, `LiteralRobotCommand`, `ToggleRobotCommand`, `TypedRobotCommand`, `RobotCommandRecord` y `parse_commands`.

- [ ] **Step 4: Crear `responses.py` — mitad respuestas**

Agregar al final de `controller/robot/responses.py`:

```python
class RobotResponse:
    """Algo que sale del robot hacia el usuario.

    `request_id` es el valor que se copia al campo `id` del sobre JSON-RPC, no el
    criterio para elegir el sobre: eso lo decide el tipo concreto (ver `to_jsonrpc`).
    Sólo las subclases de despacho lo setean.
    """

    request_id: Final[str | int | None]

    def __init__(self, request_id: str | int | None = None) -> None:
        self.request_id = request_id

    @override
    def __str__(self) -> str:
        return type(self).__name__


class StrRobotResponse(RobotResponse):
    """Output crudo del robot (una línea del Arduino, un mensaje suelto)."""

    text: Final[str]

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    @override
    def __str__(self) -> str:
        return self.text


class CommandsDescriptionRobotResponse(RobotResponse):
    """Los descriptores de comandos que el robot publicó (autodescubrimiento)."""

    commands: Final[RobotCommandRecord]

    def __init__(self, commands: RobotCommandRecord) -> None:
        super().__init__()
        self.commands = commands

    def toList(self) -> list[dict[str, Any]]:
        return self.commands.toList()


class StatusRobotResponse(RobotResponse):
    """Snapshot de telemetría. Lo produce el loop periódico, no el robot."""

    status: Final[dict[str, Any]]

    def __init__(self, status: dict[str, Any]) -> None:
        super().__init__()
        self.status = status


class DispatchOkRobotResponse(RobotResponse):
    """El comando se validó y salió. NO afirma que el robot lo haya ejecutado."""

    method: Final[str]
    detail: Final[str]
    commands_count: Final[int | None]

    def __init__(
        self,
        request_id: str | int | None,
        method: str,
        detail: str = SENT_ACK,
        commands_count: int | None = None,
    ) -> None:
        super().__init__(request_id)
        self.method = method
        self.detail = detail
        self.commands_count = commands_count

    @override
    def __str__(self) -> str:
        return self.detail


class DispatchErrorRobotResponse(RobotResponse):
    """El comando no se pudo despachar: inválido, o falló el transporte."""

    method: Final[str]
    error: Final[Exception]

    def __init__(
        self, request_id: str | int | None, method: str, error: Exception
    ) -> None:
        super().__init__(request_id)
        self.method = method
        self.error = error

    @override
    def __str__(self) -> str:
        return str(self.error)
```

- [ ] **Step 5: Correr el test y verificar que pasa**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_responses.py']))
"
```

Esperado: PASS (18 tests).

- [ ] **Step 6: Commit**

```bash
git add services/PiSystemAgent/controller/robot/responses.py \
        services/PiSystemAgent/controller/tests/test_responses.py
git commit -m "refactor(pi): extraer el vocabulario de respuestas y comandos a responses.py

El arbol de tipos vivia dentro de ros2_controller.py, lo que obligaba al
mock y al serial a importar del modulo de ROS 2. La clase base pierde el
__str__ roto (devolvia None) y gana request_id; aparecen los tipos de
despacho y de telemetria."
```

---

### Task 2: `dispatch()` y `to_jsonrpc()`

Agrega las dos funciones nuevas a `json_rpc.py`. El `handle_json_rpc` viejo sigue vivo y funcionando: se borra en la tarea 4.

**Files:**
- Modify: `services/PiSystemAgent/controller/json_rpc.py`
- Create: `services/PiSystemAgent/controller/tests/test_json_rpc.py`

**Interfaces:**
- Consumes: todo el árbol de `controller.robot.responses` (Task 1).
- Produces:
  - `async def dispatch(command: JsonRpcCommand, robot) -> RobotResponse`
  - `def to_jsonrpc(resp: RobotResponse) -> JsonRpcResponse | JsonRpcNotification`

- [ ] **Step 1: Escribir el test que falla**

Crear `controller/tests/test_json_rpc.py`:

```python
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
```

- [ ] **Step 2: Correr el test y verificar que falla**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_json_rpc.py']))
"
```

Esperado: `ImportError: cannot import name 'dispatch' from 'controller.json_rpc'`.

- [ ] **Step 3: Cambiar los imports de `json_rpc.py`**

**Cuidado con la colisión de nombres.** Durante esta tarea conviven dos árboles de tipos:
el viejo (todavía dentro de `ros2_controller.py`, el que producen los tres controladores sin
migrar) y el nuevo (`responses.py`). Son clases **distintas con el mismo nombre**. Si se
reapunta el nombre `CommandsDescriptionRobotResponse` al módulo nuevo, los `isinstance` de
`handle_json_rpc` dejan de matchear contra lo que los controladores siguen produciendo y todo
cae en la rama `else` — el árbol se pondría rojo acá en vez de en la Task 4.

Por eso el árbol viejo se importa **con alias** mientras `handle_json_rpc` siga vivo.
Reemplazar el bloque de import de las líneas 15-19 de `controller/json_rpc.py` por:

```python
# Árbol nuevo: lo usan dispatch() y to_jsonrpc().
from .robot.responses import (
    CommandsDescriptionRobotResponse,
    DispatchErrorRobotResponse,
    DispatchOkRobotResponse,
    RobotResponse,
    StatusRobotResponse,
    StrRobotResponse,
)

# Árbol viejo: lo usa SÓLO handle_json_rpc, que se borra en la Task 4 junto con estos
# imports. Van con alias porque son clases distintas que comparten nombre con las de arriba.
from .robot.ros2_controller import (
    CommandErrorRobotResponse as _LegacyCommandErrorRobotResponse,
    CommandsDescriptionRobotResponse as _LegacyCommandsDescriptionRobotResponse,
    RobotResponse as _LegacyRobotResponse,
)
```

Y dentro de `handle_json_rpc`, renombrar los tres usos a sus alias: la anotación
`response: _LegacyRobotResponse`, `isinstance(resp, _LegacyCommandErrorRobotResponse)` (dos
ocurrencias) e `isinstance(resp, _LegacyCommandsDescriptionRobotResponse)` (una).

Nada más de `handle_json_rpc` cambia en esta tarea: sigue funcionando igual, con los dos
fallos conocidos de `test_ros2.py`.

- [ ] **Step 4: Implementar `dispatch()`**

Agregar al final de `controller/json_rpc.py`:

```python
async def dispatch(command: JsonRpcCommand, robot) -> RobotResponse:
    """Despacha un comando y devuelve SÓLO el resultado del despacho.

    "Despacho" = el comando se validó contra el descriptor y se escribió/publicó.
    No afirma que el robot lo haya ejecutado: su salida real llega por otro camino
    (el loop de respuestas) y sale como notification sin id.

    Nunca levanta: traduce los fallos esperables a DispatchErrorRobotResponse para
    que el core no se caiga por un comando malo (hoy una excepción acá escapa del
    TaskGroup de MicroCore y tumba el agente entero).
    """
    loop = asyncio.get_running_loop()

    try:
        if command.method == "execute_sequence":
            commands = command.params.get("commands", [])
            if not isinstance(commands, list):
                raise ValueError("'commands' debe ser una lista")

            await loop.run_in_executor(None, robot.execute_sequence, commands)
            return DispatchOkRobotResponse(
                command.id, command.method, commands_count=len(commands)
            )

        raw_command = command.params.get("command", command.method)
        await loop.run_in_executor(None, robot.send_command, raw_command)
        return DispatchOkRobotResponse(command.id, command.method)

    except (ValueError, ConnectionError, OSError) as e:
        logger.error("Error despachando comando '%s': %s", command.method, e)
        return DispatchErrorRobotResponse(command.id, command.method, e)
```

- [ ] **Step 5: Implementar `to_jsonrpc()`**

Agregar al final de `controller/json_rpc.py`:

```python
# Mapeo de causa → código JSON-RPC. InvalidCommandError hereda de ValueError, así que
# el orden importa sólo para legibilidad: ambos caen en -32602.
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


def _error_code(error: Exception) -> int:
    if isinstance(error, ValueError):
        return _INVALID_PARAMS
    if isinstance(error, (ConnectionError, OSError)):
        return _INTERNAL_ERROR
    return _INTERNAL_ERROR


def to_jsonrpc(resp: RobotResponse) -> JsonRpcResponse | JsonRpcNotification:
    """Traduce un RobotResponse al sobre JSON-RPC que le corresponde.

    El TIPO decide el sobre, no el valor de `request_id`: el cliente puede no mandar
    id, y un resultado de despacho sigue siendo una respuesta aunque su id sea null.
    """
    if isinstance(resp, DispatchOkRobotResponse):
        return JsonRpcResponse(
            result=JsonRpcResult(
                status="ok",
                method=resp.method,
                response=resp.detail,
                commands_count=resp.commands_count,
            ),
            id=resp.request_id,
        )

    if isinstance(resp, DispatchErrorRobotResponse):
        return JsonRpcResponse(
            error=JsonRpcError(code=_error_code(resp.error), message=str(resp.error)),
            id=resp.request_id,
        )

    if isinstance(resp, CommandsDescriptionRobotResponse):
        return JsonRpcNotification(
            method="command.update", params={"commands": resp.toList()}
        )

    if isinstance(resp, StatusRobotResponse):
        return JsonRpcNotification(method="status.update", params=resp.status)

    if isinstance(resp, StrRobotResponse):
        return JsonRpcNotification(method="robot.output", params={"data": resp.text})

    logger.warning("RobotResponse sin traducción específica: %s", type(resp).__name__)
    return JsonRpcNotification(method="robot.output", params={"data": str(resp)})
```

- [ ] **Step 6: Correr el test y verificar que pasa**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_json_rpc.py']))
"
```

Esperado: PASS (17 tests).

- [ ] **Step 7: Verificar que no se rompió nada existente**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_responses.py', 'controller/tests/test_json_rpc.py', 'controller/tests/test_ros2.py', 'controller/tests/test_ws_strategy.py']))
"
```

Esperado: los nuevos pasan; `test_ros2.py` sigue con los 2 fallos conocidos (`test_read_response_returns_synthetic_ack` y `test_strategy_send_publishes_and_acks`), que se resuelven en la Task 4.

- [ ] **Step 8: Commit**

```bash
git add services/PiSystemAgent/controller/json_rpc.py \
        services/PiSystemAgent/controller/tests/test_json_rpc.py
git commit -m "feat(pi): agregar dispatch() y to_jsonrpc() al adapter JSON-RPC

dispatch() devuelve solo el resultado del despacho, con el id del comando.
to_jsonrpc() elige el sobre por TIPO de RobotResponse, no por si hay id:
el cliente puede no mandarlo y un despacho sigue siendo una respuesta.

handle_json_rpc sigue vivo; se borra al migrar las strategies."
```

---

### Task 3: `OutboxLocalStrategy`

La base compartida que aporta la cola y lo que la toca. Nadie hereda de ella todavía.

**Files:**
- Modify: `services/PiSystemAgent/controller/strategy/base.py`
- Create: `services/PiSystemAgent/controller/tests/test_outbox_strategy.py`

**Interfaces:**
- Consumes: `dispatch`, `to_jsonrpc` (Task 2); `RobotResponse`, `StatusRobotResponse` (Task 1).
- Produces: `OutboxLocalStrategy(LocalStrategy, ABC)` con `_outbox`, `_robot`, `receive()`, `send()`, `_start_loops()`, `_stop_loops()`, `get_telemetry_enabled()`, `set_telemetry()`, y la constante `STATUS_INTERVAL_SEC = 5.0`.

- [ ] **Step 1: Escribir el test que falla**

Crear `controller/tests/test_outbox_strategy.py`:

```python
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
    async def scenario():
        strat = FakeStrategy()
        await strat.start()
        task = strat._response_task
        await strat.stop()
        await asyncio.sleep(0)
        return task

    task = asyncio.run(scenario())
    assert task is not None and task.done()


def test_set_telemetry_toggles_without_running_loop():
    strat = FakeStrategy()
    assert strat.get_telemetry_enabled() is True
    strat.set_telemetry(False)
    assert strat.get_telemetry_enabled() is False
```

- [ ] **Step 2: Correr el test y verificar que falla**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_outbox_strategy.py']))
"
```

Esperado: `ImportError: cannot import name 'OutboxLocalStrategy'`.

- [ ] **Step 3: Implementar `OutboxLocalStrategy`**

Agregar al final de `controller/strategy/base.py` (y agregar `import asyncio`, `import logging` arriba, más `from ..json_rpc import JsonRpcCommand, dispatch, to_jsonrpc` y `from ..robot.responses import RobotResponse, StatusRobotResponse`):

```python
logger = logging.getLogger(__name__)

STATUS_INTERVAL_SEC = 5.0


class OutboxLocalStrategy(LocalStrategy, ABC):
    """Base de las strategies locales: una cola, tres productores, un consumidor.

    Productores: `send()` (resultado del despacho, con id), `_response_loop`
    (output del robot) y `_telemetry_loop` (snapshot periódico). Consumidor:
    `receive()`, único lugar donde se traduce a JSON-RPC.

    Las subclases construyen `self._robot` en su `__init__` y manejan `start`/`stop`,
    que es donde genuinamente difieren (el mock conecta sync; serial y ROS 2 van a
    executor).
    """

    _robot: Any

    def __init__(self) -> None:
        self._outbox: asyncio.Queue[RobotResponse] = asyncio.Queue()
        self._telemetry_enabled: bool = True
        self._telemetry_task: asyncio.Task[None] | None = None
        self._response_task: asyncio.Task[None] | None = None

    # --- interfaz Strategy ---

    @override
    async def send(self, message: Any) -> None:
        """Despacha el comando. La respuesta correlacionada entra a la misma cola."""
        command = JsonRpcCommand.model_validate(message)
        await self._outbox.put(await dispatch(command, self._robot))

    @override
    async def receive(self) -> Any:
        """Único punto de traducción a JSON-RPC."""
        resp = await self._outbox.get()
        return to_jsonrpc(resp).model_dump(mode="json")

    @override
    def get_telemetry_enabled(self) -> bool:
        return self._telemetry_enabled

    @override
    def set_telemetry(self, enabled: bool) -> None:
        self._telemetry_enabled = enabled
        if enabled and (self._telemetry_task is None or self._telemetry_task.done()):
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())
        elif not enabled and self._telemetry_task and not self._telemetry_task.done():
            _ = self._telemetry_task.cancel()
            self._telemetry_task = None
        logger.info(
            "Telemetría %s %s", self.name, "habilitada" if enabled else "deshabilitada"
        )

    # --- loops ---

    def _start_loops(self) -> None:
        self._response_task = asyncio.create_task(self._response_loop())
        if self._telemetry_enabled:
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())

    async def _stop_loops(self) -> None:
        """Cancela los loops. El llamador debe haber llamado `robot.stop_reading()`
        ANTES: `asyncio.to_thread` no se puede cancelar mientras el hilo está
        bloqueado, así que el sentinel es lo que realmente lo desbloquea."""
        for task in (self._response_task, self._telemetry_task):
            if task and not task.done():
                _ = task.cancel()
        self._response_task = None
        self._telemetry_task = None

    async def _response_loop(self) -> None:
        """Drena el output del robot de forma continua, haya usuario o no.

        Que este loop sea independiente de `send()` es lo que impide que la lista de
        respuestas del controlador crezca sin tope y que una ráfaga acumulada salga
        de golpe pegada a un comando no relacionado.
        """
        try:
            while True:
                resp = await asyncio.to_thread(self._robot.read_response)
                if resp is None:  # sentinel de parada
                    return
                await self._outbox.put(resp)
        except asyncio.CancelledError:
            pass
        except (ConnectionError, OSError) as e:
            logger.error("Loop de respuestas detenido por error de E/S: %s", e)

    async def _telemetry_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(STATUS_INTERVAL_SEC)
                await self._outbox.put(StatusRobotResponse(self._robot.get_status()))
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 4: Correr el test y verificar que pasa**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_outbox_strategy.py']))
"
```

Esperado: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add services/PiSystemAgent/controller/strategy/base.py \
        services/PiSystemAgent/controller/tests/test_outbox_strategy.py
git commit -m "feat(pi): OutboxLocalStrategy — una cola, tres productores, un consumidor

El loop de respuestas drena el output del robot de forma continua, sin
depender de que el usuario mande comandos. Traduccion a JSON-RPC en un
solo lugar (receive)."
```

---

### Task 4: El flip — contrato nuevo en los tres controladores y las tres strategies

Cambia el contrato de los controladores y migra las strategies. **El árbol queda rojo entre el paso 3 y el paso 14**: `handle_json_rpc` es compartido por las tres strategies, así que no hay forma de migrar una sola sin romper las otras dos.

**Files:**
- Modify: `services/PiSystemAgent/controller/robot/ros2_controller.py`
- Modify: `services/PiSystemAgent/controller/robot/robot_mock_controller.py`
- Modify: `services/PiSystemAgent/controller/robot/robot_controller.py`
- Modify: `services/PiSystemAgent/controller/strategy/local/ros2_strategy.py`
- Modify: `services/PiSystemAgent/controller/strategy/local/mock_strategy.py`
- Modify: `services/PiSystemAgent/controller/strategy/local/serial_strategy.py`
- Modify: `services/PiSystemAgent/controller/json_rpc.py`
- Modify: `services/PiSystemAgent/controller/tests/test_ros2.py`

**Interfaces:**
- Consumes: `responses.py` (Task 1), `dispatch`/`to_jsonrpc` (Task 2), `OutboxLocalStrategy` (Task 3).
- Produces: el contrato uniforme del controlador declarado en Global Constraints.

- [ ] **Step 1: Escribir los tests que fallan — contrato de `Ros2Controller`**

En `controller/tests/test_ros2.py`, **borrar** estos tests (su contrato ya no existe): `test_read_response_returns_synthetic_ack`, `test_send_command_rejects_unknown_command`, `test_parse_commands_literal_and_toggle_and_typed`, `test_parse_commands_skips_malformed_toggle`, `test_toggle_todict_is_json_serializable`, `test_typed_uint_valid`, `test_record_valid_fails_open_before_discovery` (los cinco últimos se mudaron a `test_responses.py` en la Task 1).

Ajustar el import del tope del archivo a:

```python
from controller.robot import ros2_controller
from controller.robot.responses import (
    CommandsDescriptionRobotResponse, InvalidCommandError, StrRobotResponse,
)
from controller.robot.ros2_controller import Ros2Controller, parse_key_value
from controller.strategy.local.ros2_strategy import Ros2Strategy
```

Y **agregar** estos tests:

```python
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
```

- [ ] **Step 2: Correr y verificar que fallan**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_ros2.py']))
"
```

Esperado: fallos por `AttributeError: 'Ros2Controller' object has no attribute 'stop_reading'` y porque `send_command` no levanta.

- [ ] **Step 3: Migrar `Ros2Controller`** *(a partir de acá el árbol queda rojo)*

En `controller/robot/ros2_controller.py`:

1. Borrar las líneas **29-236** (de `# Ack sintético...` hasta el final de `ComposedRobotResponse`), es decir los dos árboles de tipos. Conservar `parse_key_value` y `Ros2Controller`.
2. Reemplazar los imports del tope por:

```python
import logging
import os
import threading
import queue
from typing import Any

from .responses import (
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
    RobotCommandRecord,
    RobotResponse,
    parse_commands,
)

logger = logging.getLogger(__name__)
```

3. En `__init__`, reemplazar el par lista+lock por una cola:

```python
        self._responses: queue.Queue[RobotResponse | None] = queue.Queue()
```

(borrar `self.robot_response` y `self._robot_response_lock`).

4. En `_handle_data`, reemplazar el bloque del `with self._robot_response_lock:` por:

```python
        if isinstance(msg.data, str) and msg.data.startswith("commands="):  # pyright: ignore[reportUnknownMemberType]
            self.robot_commands = parse_commands(msg.data)
            self._responses.put(CommandsDescriptionRobotResponse(self.robot_commands))
```

5. Reemplazar `send_command` completo por:

```python
    def send_command(self, command: str):
        if not self._connected or self._publisher is None:
            raise ConnectionError(
                "Ros2Controller no conectado. Llama a connect() primero."
            )

        if not self.robot_commands.valid(command):
            self.logger.warning("Comando inválido: %s", command)
            raise InvalidCommandError(f"comando desconocido: {command}")

        msg = self._string_cls()
        msg.data = command
        self._publisher.publish(msg)
        self.logger.info("Comando publicado en %s: %s", self.command_topic, command)
```

6. Reemplazar `read_response` completo por:

```python
    def read_response(self) -> RobotResponse | None:
        """Bloquea hasta que el robot emita algo. None = señal de parada."""
        return self._responses.get()

    def stop_reading(self) -> None:
        """Desbloquea un read_response() en curso. Idempotente."""
        self._responses.put(None)
```

7. En `disconnect()`, agregar `self.stop_reading()` como primera línea.

- [ ] **Step 4: Correr los tests de ROS 2**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_ros2.py', '-k', 'not strategy']))
"
```

Esperado: PASS. Los `-k strategy` siguen rojos hasta el paso 11.

- [ ] **Step 5: Escribir el test del mock**

Crear `controller/tests/test_mock_controller.py`:

```python
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
```

- [ ] **Step 6: Migrar `RobotMockController`**

Reemplazar `controller/robot/robot_mock_controller.py` entero por:

```python
import logging
import queue
import random
from typing import Any

from .responses import (
    CommandsDescriptionRobotResponse,
    InvalidCommandError,
    LiteralRobotCommand,
    RobotCommandRecord,
    RobotResponse,
    StrRobotResponse,
    ToggleRobotCommand,
)


class RobotMockController:
    """Robot simulado. Replica el contrato real, validación de comandos incluida,
    para que el modo demo ejercite de verdad el autodescubrimiento."""

    arduino_port: str

    def __init__(self, arduino_port: str):
        self.arduino_port = arduino_port
        self.logger = logging.getLogger(__name__)
        self.logger.warning(
            "RobotMockController is active. No physical robot commands will be sent."
        )

        self.robot_commands: RobotCommandRecord = RobotCommandRecord([
            ToggleRobotCommand("play", "start", "stop"),
            LiteralRobotCommand("restart"),
        ])
        self._responses: queue.Queue[RobotResponse | None] = queue.Queue()

    def connect(self):
        # Publicar los descriptores al conectar imita al agente real, que los manda
        # por telemetría apenas arranca.
        self._responses.put(CommandsDescriptionRobotResponse(self.robot_commands))
        self.logger.info("Mock robot connected (no-op).")

    def disconnect(self):
        self.stop_reading()
        self.logger.info("Mock robot disconnected (no-op).")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def send_command(self, command: str):
        if not self.robot_commands.valid(command):
            self.logger.warning("Comando inválido: %s", command)
            raise InvalidCommandError(f"comando desconocido: {command}")

        self.logger.info("Mock robot received command: %s", command)
        self._responses.put(StrRobotResponse("OK"))

    def read_response(self) -> RobotResponse | None:
        return self._responses.get()

    def stop_reading(self) -> None:
        self._responses.put(None)

    def execute_sequence(self, commands: list[str]):
        self.logger.info("Mock robot executing command sequence (simulated):")
        for command in commands:
            if command:
                self.send_command(command)

    def get_status(self) -> dict[str, Any]:
        """Retorna estado simulado del robot mock."""
        return {
            "status": "online",
            "mock": True,
            "sensors": {
                "base": random.randint(0, 180),
                "cuerpo": random.randint(0, 180),
                "hombro": random.randint(0, 180),
                "brazo": random.randint(0, 180),
                "antebrazo_1": random.randint(0, 180),
                "antebrazo_2": random.randint(0, 180),
                "mano": random.randint(0, 180),
            },
        }
```

- [ ] **Step 7: Correr los tests del mock**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_mock_controller.py']))
"
```

Esperado: PASS (4 tests).

- [ ] **Step 8: Escribir el test del serial**

Crear `controller/tests/test_serial_controller.py`:

```python
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
```

- [ ] **Step 9: Migrar `RobotController` (serial)**

En `controller/robot/robot_controller.py`:

1. Reemplazar el import `from .ros2_controller import RobotResponse, StrRobotResponse` por `from .responses import RobotResponse, StrRobotResponse`.
2. Agregar `import threading` y, en `__init__`, `self._stop = threading.Event()`.
3. Reemplazar `read_response` por:

```python
    def read_response(self) -> RobotResponse | None:
        """Bloquea hasta que el Arduino emita una línea. None = señal de parada.

        El puerto tiene timeout=1, así que readline() devuelve b'' cada segundo sin
        datos. Esos vacíos se descartan: son el punto donde se chequea la parada.
        """
        if not self.ser or not self.ser.is_open:
            raise ConnectionError("Arduino not connected. Call connect() first.")

        while not self._stop.is_set():
            try:
                line = self.ser.readline().decode("utf-8").strip()
            except serial.SerialException as e:
                raise EnvironmentError(
                    f"Error reading response from Arduino: {e}"
                ) from e
            if line:
                self.logger.info("Received response: %s", line)
                return StrRobotResponse(line)

        return None

    def stop_reading(self) -> None:
        """Desbloquea un read_response() en curso (a más tardar en un timeout)."""
        self._stop.set()
```

4. Reemplazar `execute_sequence` por (sin leer):

```python
    def execute_sequence(self, commands: list[str]):
        self.logger.info("Executing command sequence...")
        for command in commands:
            if command:
                self.send_command(command)
```

5. En `disconnect()`, agregar `self.stop_reading()` como primera línea.

- [ ] **Step 10: Correr los tests del serial**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q', 'controller/tests/test_serial_controller.py']))
"
```

Esperado: PASS (4 tests).

- [ ] **Step 11: Migrar las tres strategies**

Reemplazar `controller/strategy/local/ros2_strategy.py` entero por:

```python
"""Strategy local: comunicación con el robot vía ROS 2 (IPC interno de la Pi)."""

import asyncio
import logging
from typing import override

from ...robot.ros2_controller import Ros2Controller
from ..base import OutboxLocalStrategy, State

logger = logging.getLogger(__name__)


class Ros2Strategy(OutboxLocalStrategy):
    """Wrappea Ros2Controller. La cola, los loops y la traducción a JSON-RPC los
    aporta OutboxLocalStrategy; acá sólo vive el ciclo de vida del nodo."""

    def __init__(
        self,
        *,
        node_name: str,
        command_topic: str,
        data_topic: str,
        domain_id: int = 42,
    ):
        super().__init__()
        self._robot: Ros2Controller = Ros2Controller(
            node_name=node_name,
            command_topic=command_topic,
            data_topic=data_topic,
            domain_id=domain_id,
        )

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.connect)
        self._start_loops()
        self._state = State.RUNNING
        logger.info("Ros2Strategy iniciado (node: %s)", self._robot.node_name)

    @override
    async def stop(self) -> None:
        # stop_reading ANTES de cancelar: to_thread no se puede cancelar mientras el
        # hilo está bloqueado en read_response.
        self._robot.stop_reading()
        await self._stop_loops()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._robot.disconnect)
        self._state = State.STOPPED
        logger.info("Ros2Strategy detenido")

    @override
    async def pause(self) -> None:
        self.set_telemetry(False)
        await super().pause()
        logger.info("Ros2Strategy pausado")

    @override
    async def resume(self) -> None:
        self.set_telemetry(True)
        await super().resume()
        logger.info("Ros2Strategy reanudado")
```

Reemplazar `controller/strategy/local/serial_strategy.py` entero por el mismo esqueleto, cambiando: el docstring del módulo a `"""Strategy local: comunicación serial con Arduino."""`, el import a `from ...robot.robot_controller import RobotController`, la clase a `class SerialStrategy(OutboxLocalStrategy):`, el `__init__` a `def __init__(self, arduino_port: str): super().__init__(); self._robot: RobotController = RobotController(arduino_port)`, y los mensajes de log a `SerialStrategy` (el de `start` usa `self._robot.arduino_port`).

Reemplazar `controller/strategy/local/mock_strategy.py` entero por el mismo esqueleto, con: import `from ...robot.robot_mock_controller import RobotMockController`, clase `MockStrategy(OutboxLocalStrategy)`, `__init__` igual al de serial pero construyendo `RobotMockController(arduino_port)`, y `start`/`stop` **sin executor** (el mock conecta sync):

```python
    @override
    async def start(self) -> None:
        self._robot.connect()
        self._start_loops()
        self._state = State.RUNNING
        logger.info("MockStrategy iniciado")

    @override
    async def stop(self) -> None:
        self._robot.stop_reading()
        await self._stop_loops()
        self._robot.disconnect()
        self._state = State.STOPPED
        logger.info("MockStrategy detenido")
```

- [ ] **Step 12: Borrar `handle_json_rpc` y su import muerto**

En `controller/json_rpc.py`:
1. Borrar la función `handle_json_rpc` completa y la función auxiliar `_error_response` (ya no la usa nadie).
2. Borrar `from .robot.ros2_controller import CommandErrorRobotResponse` (el import temporal del Task 2 Step 3).
3. Borrar `CommandErrorRobotResponse` y `CommandsDescriptionRobotResponse` de los imports si quedaron sin uso; dejar sólo lo que usan `dispatch`/`to_jsonrpc`.
4. Borrar `from collections.abc import AsyncGenerator` si quedó sin uso.

- [ ] **Step 13: Actualizar el test de strategy en `test_ros2.py`**

Reemplazar `test_strategy_send_publishes_and_acks` por:

```python
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
```

- [ ] **Step 14: Correr toda la suite** *(el árbol vuelve a verde acá)*

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, pytest
sys.argv = ['pytest']
sys.exit(pytest.main(['-q',
  'controller/tests/test_responses.py',
  'controller/tests/test_json_rpc.py',
  'controller/tests/test_outbox_strategy.py',
  'controller/tests/test_mock_controller.py',
  'controller/tests/test_serial_controller.py',
  'controller/tests/test_ros2.py',
  'controller/tests/test_ws_strategy.py',
  'controller/tests/test_camera_relay.py',
]))
"
```

Esperado: PASS, cero fallos. Si algo falla, arreglarlo antes de commitear — este paso es la verificación del flip completo.

- [ ] **Step 15: Commit**

```bash
git add services/PiSystemAgent/controller
git commit -m "refactor(pi)!: desacoplar el despacho del envio de respuestas

Los tres controladores pasan al mismo contrato: send_command levanta en
vez de acumular, read_response bloquea y devuelve UNO, stop_reading lo
desbloquea. Las tres strategies heredan de OutboxLocalStrategy.

- #3: el id del comando viaja en DispatchOk/Error y to_jsonrpc lo emite
- #4: el serial deja de usar \"\" como centinela de correlacion
- #7: el loop de respuestas drena de continuo, sin usuario y sin rafagas
- #11: la clase base pierde el __str__ que devolvia None
- #12: una sola forma de error, con codigos JSON-RPC reales

handle_json_rpc y ComposedRobotResponse desaparecen."
```

---

### Task 5: Verificación end-to-end en modo demo y documentación

**Files:**
- Modify: `services/PiSystemAgent/CLAUDE.md`
- Modify: `services/PiSystemAgent/ARQUITECTURA.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: nada de código.

- [ ] **Step 1: Verificar el modo demo end-to-end**

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, asyncio, json
sys.argv = ['x']
from controller.strategy.local.mock_strategy import MockStrategy

async def main():
    s = MockStrategy('/dev/null')
    await s.start()
    await s.send({'jsonrpc':'2.0','method':'move','params':{'command':'start'},'id':1})
    await s.send({'jsonrpc':'2.0','method':'jump','id':2})
    for _ in range(4):
        print(json.dumps(await asyncio.wait_for(s.receive(), 2.0)))
    await s.stop()

asyncio.run(main())
"
```

Esperado, en algún orden (no se garantiza el orden entre el ack de despacho y el output del robot):
- una notification `command.update` con el toggle `play` y el literal `restart`, con los `true`/`false` como dicts anidados;
- una respuesta `{"result": {"status": "ok", "method": "move", "response": "mensaje enviado"}, "id": 1}`;
- una notification `robot.output` con `{"data": "OK"}`;
- una respuesta de error con `"id": 2` y `"code": -32602` (el comando `jump` no está en los descriptores).

Si falta alguno o el proceso cuelga, no seguir: es un fallo del flip.

- [ ] **Step 2: Verificar que el core no se cae con un comando inválido**

El bug original tumbaba el `TaskGroup` de `MicroCore`. Confirmar que ahora el error es un dato, no una excepción:

```bash
cd services/PiSystemAgent && uv run python -c "
import sys, asyncio, json
sys.argv = ['x']
from controller.strategy.local.mock_strategy import MockStrategy

async def main():
    s = MockStrategy('/dev/null')
    await s.start()
    for i in range(3):
        await s.send({'jsonrpc':'2.0','method':'jump','id':i})
    print('el agente sigue vivo tras 3 comandos invalidos')
    await s.stop()

asyncio.run(main())
"
```

Esperado: imprime el mensaje, sin traceback.

- [ ] **Step 3: Actualizar `ARQUITECTURA.md`**

En la sección que describe el flujo de comandos, reemplazar la descripción del flujo request→response por el modelo nuevo: tres productores (despacho, loop de respuestas, loop de telemetría), una cola de `RobotResponse` por strategy local, un consumidor que traduce a JSON-RPC en `receive()`. Documentar el contrato del controlador (`send_command` levanta, `read_response` bloquea y devuelve uno o `None`, `stop_reading` desbloquea) y la regla de correlación: el tipo decide el sobre, `request_id` sólo rellena el campo `id`.

- [ ] **Step 4: Actualizar `CLAUDE.md` de PiSystemAgent**

En el árbol de "Estructura del Código", agregar `responses.py` bajo `robot/` con la descripción "Vocabulario de dominio: árbol RobotResponse + descriptores de comandos". En `strategy/base.py`, agregar la mención de `OutboxLocalStrategy`. Agregar los tres archivos de test nuevos bajo `tests/`.

- [ ] **Step 5: Commit**

```bash
git add services/PiSystemAgent/ARQUITECTURA.md services/PiSystemAgent/CLAUDE.md
git commit -m "docs(pi): documentar el desacople de despacho y respuestas"
```
