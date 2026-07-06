# Resiliencia y reconexión Api↔RaspberryPi↔WebClient Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que la Api detecte caídas de la Pi y del usuario (silenciosas o limpias) y se recupere sin intervención manual, y que el WebClient reconecte solo cuando cae la Api — sin recargar la página.

**Architecture:** Heartbeat de aplicación (ping/pong) reutilizado en ambas conexiones que gestiona la Api (`/m2m/robot/connect` y `/user/robot/send_command`). Del lado Api↔Pi: cierre limpio = teardown inmediato del pipe; timeout de heartbeat = el pipe entra en estado "esperando reconexión" (con `asyncio.Event` por `robot_id`) y se retoma solo si la Pi reconecta a tiempo. Del lado Api↔Usuario: cualquier motivo de desconexión es fatal para el pipe. Del lado WebClient: watchdog de heartbeat + reconexión con backoff 1s→30s, igual que ya hace `WsStrategy` en la Pi.

**Tech Stack:** Python 3.13 (FastAPI, pytest) para Api; Python 3.12 (asyncio, websockets, pytest) para RaspberryPi; Vue 3 + TypeScript (composables) para WebClient.

## Global Constraints

- Spec de referencia: `docs/superpowers/specs/2026-07-06-resiliencia-reconexion-design.md` — toda ambigüedad se resuelve releyendo ese documento.
- No persistir estado online/offline en DB (vive en memoria en `RobotConnectionRepository`).
- No bufferizar comandos de usuario durante una desconexión del robot — se rechazan de inmediato (esto ya es responsabilidad de la validación existente del lado Api cuando no hay pipe activo; no se agrega buffering en ningún paso de este plan).
- No tocar la lógica de reconexión ya existente en `WsStrategy` (backoff 1s→30s + re-auth HTTP) — solo se le agrega interceptación de ping/pong y un watchdog nuevo, sin modificar `_reconnect`/`_authenticate`/`_connect_ws`.
- Heartbeat: intervalo de ping 10s, timeout de pong 15s (constantes `PING_INTERVAL_SECONDS`/`PONG_TIMEOUT_SECONDS` en `services/Api/src/robot/utils/heartbeat.py`). Watchdog del lado receptor (Pi, WebClient): timeout de 25s sin ver un ping nuevo.
- Timeout de espera de reconexión del robot en el pipe: 120s (constante `_ROBOT_RECONNECT_WAIT_SECONDS` en `services/Api/src/robot/repositories/stream_entities.py`).
- Todos los tests nuevos de Python siguen el patrón ya usado en el repo: `pytest` plano (sin `pytest-asyncio`), cuerpos async envueltos en una función local `async def run(): ...` y ejecutados con `asyncio.run(run())`.
- WebClient no tiene infraestructura de tests automatizados (no hay vitest ni ningún `*.test.*` en el repo) — las tareas de WebClient se verifican manualmente, documentado explícitamente en cada tarea.

---

## Mapa de archivos

**Api (`services/Api/`):**
- Crear: `src/robot/utils/heartbeat.py`
- Modificar: `src/robot/utils/__init__.py`
- Modificar: `src/robot/adapters/proxy_stream_source.py`
- Modificar: `src/robot/adapters/user_stream_source.py`
- Modificar: `src/robot/adapters/__init__.py`
- Modificar: `src/robot/repositories/robot_connection.py`
- Modificar: `src/robot/repositories/stream_entities.py`
- Modificar: `src/robot/routes/m2m.py`
- Modificar: `src/robot/services/ipc_user_robot_comunication.py`
- Crear: `tests/robot/utils/__init__.py`, `tests/robot/utils/test_heartbeat.py`
- Modificar: `tests/robot/adapters/test_proxy_stream_source.py`
- Modificar: `tests/robot/adapters/test_user_stream_source.py`
- Modificar: `tests/robot/repositories/test_robot_connection.py`
- Crear: `tests/robot/repositories/test_stream_entities.py`

**RaspberryPi (`services/RaspberryPi/`):**
- Modificar: `controller/strategy/remote/ws_strategy.py`
- Crear: `controller/tests/test_ws_strategy.py`

**WebClient (`services/WebClient/`):**
- Modificar: `src/composables/useRobotSocket.ts`
- Modificar: `src/pages/RobotControlPage.vue`

---

### Task 1: Api — util de heartbeat (ping/pong reutilizable)

**Files:**
- Create: `services/Api/src/robot/utils/heartbeat.py`
- Modify: `services/Api/src/robot/utils/__init__.py`
- Create: `services/Api/tests/robot/utils/__init__.py`
- Test: `services/Api/tests/robot/utils/test_heartbeat.py`

**Interfaces:**
- Produces: `HeartbeatTimeoutError` (excepción), `run_heartbeat_watchdog(send_ping: Callable[[], Awaitable[None]], pong_received: asyncio.Event, *, ping_interval: float = 10.0, pong_timeout: float = 15.0) -> Never` — usado por Task 6 (m2m.py) y Task 7 (ipc_user_robot_comunication.py).

- [ ] **Step 1: Crear el paquete de tests `tests/robot/utils/`**

Crear `services/Api/tests/robot/utils/__init__.py` vacío (sigue el patrón de los demás paquetes de test, ej. `tests/robot/adapters/__init__.py`).

- [ ] **Step 2: Escribir el test que falla**

Crear `services/Api/tests/robot/utils/test_heartbeat.py`:

```python
import asyncio
from unittest.mock import AsyncMock

import pytest

from src.robot.utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog


class TestRunHeartbeatWatchdog:
    def test_pong_a_tiempo_no_lanza_y_reintenta_pings(self):
        send_ping = AsyncMock()
        pong_received = asyncio.Event()

        async def _auto_pong():
            while True:
                await asyncio.sleep(0.005)
                pong_received.set()

        async def run():
            watchdog = asyncio.create_task(
                run_heartbeat_watchdog(
                    send_ping, pong_received, ping_interval=0.01, pong_timeout=0.05
                )
            )
            answerer = asyncio.create_task(_auto_pong())
            await asyncio.sleep(0.08)
            still_running = not watchdog.done()
            watchdog.cancel()
            answerer.cancel()
            for t in (watchdog, answerer):
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            return still_running

        assert asyncio.run(run()) is True
        assert send_ping.await_count >= 2

    def test_sin_pong_lanza_heartbeat_timeout(self):
        send_ping = AsyncMock()
        pong_received = asyncio.Event()

        async def run():
            with pytest.raises(HeartbeatTimeoutError):
                await run_heartbeat_watchdog(
                    send_ping, pong_received, ping_interval=1.0, pong_timeout=0.02
                )

        asyncio.run(run())
        send_ping.assert_awaited_once()
```

- [ ] **Step 3: Correr el test y verificar que falla**

Run: `cd services/Api && uv run pytest tests/robot/utils/test_heartbeat.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.robot.utils.heartbeat'`

- [ ] **Step 4: Implementar `heartbeat.py`**

Crear `services/Api/src/robot/utils/heartbeat.py`:

```python
"""Heartbeat de aplicación: ping periódico + timeout de pong.

Mecanismo agnóstico al transporte, reutilizado tanto para la conexión
Api↔Pi (`routes/m2m.py`) como Api↔Usuario
(`services/ipc_user_robot_comunication.py`) para detectar caídas
silenciosas que no generan un cierre de socket limpio (ver
docs/superpowers/specs/2026-07-06-resiliencia-reconexion-design.md).
"""

import asyncio
from typing import Awaitable, Callable, Never

PING_INTERVAL_SECONDS: float = 10.0
PONG_TIMEOUT_SECONDS: float = 15.0


class HeartbeatTimeoutError(Exception):
    """No se recibió el pong correspondiente dentro del timeout configurado."""


async def run_heartbeat_watchdog(
    send_ping: Callable[[], Awaitable[None]],
    pong_received: asyncio.Event,
    *,
    ping_interval: float = PING_INTERVAL_SECONDS,
    pong_timeout: float = PONG_TIMEOUT_SECONDS,
) -> Never:
    """Envía un ping cada `ping_interval` segundos y espera su pong.

    Levanta `HeartbeatTimeoutError` si no se recibe el pong dentro de
    `pong_timeout` segundos. El caller es responsable de: (1) hacer
    `pong_received.set()` cuando llega un mensaje `{"type": "pong"}`
    del peer, y (2) correr esta corutina concurrente con el loop de
    recepción física (ej. en un `asyncio.TaskGroup`), para que el
    timeout pueda efectivamente cortar la conexión.
    """
    while True:
        pong_received.clear()
        await send_ping()
        try:
            await asyncio.wait_for(pong_received.wait(), timeout=pong_timeout)
        except asyncio.TimeoutError as e:
            raise HeartbeatTimeoutError() from e
        await asyncio.sleep(ping_interval)
```

Modificar `services/Api/src/robot/utils/__init__.py` (hoy vacío):

```python
from .heartbeat import HeartbeatTimeoutError as HeartbeatTimeoutError
from .heartbeat import run_heartbeat_watchdog as run_heartbeat_watchdog
```

- [ ] **Step 5: Correr el test y verificar que pasa**

Run: `cd services/Api && uv run pytest tests/robot/utils/test_heartbeat.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add services/Api/src/robot/utils/heartbeat.py services/Api/src/robot/utils/__init__.py services/Api/tests/robot/utils/
git commit -m "feat(api): agregar util de heartbeat ping/pong reutilizable"
```

---

### Task 2: Api — `ProxyStreamSource` propaga la desconexión física

**Files:**
- Modify: `services/Api/src/robot/adapters/proxy_stream_source.py`
- Modify: `services/Api/src/robot/adapters/__init__.py`
- Test: `services/Api/tests/robot/adapters/test_proxy_stream_source.py`

**Interfaces:**
- Consumes: nada nuevo (no depende de Task 1).
- Produces: `ProxyStreamDisconnected(reason: str)` (excepción, atributo `.reason`), `ProxyStreamSource.mark_disconnected(reason: str) -> None`. Usado por Task 6 (m2m.py) y consumido indirectamente por Task 5 (el pipe recibe esta excepción desde `RobotConnection.connect()`).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `services/Api/tests/robot/adapters/test_proxy_stream_source.py` (mantener los imports existentes y agregar `pytest.raises`, que el archivo ya usa):

```python
from src.robot.adapters.proxy_stream_source import ProxyStreamDisconnected


class TestMarkDisconnected:
    def test_receive_data_pendiente_levanta_disconnected(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data empiece a esperar
            await source.mark_disconnected("timeout")
            with pytest.raises(ProxyStreamDisconnected) as exc_info:
                await task
            return exc_info.value.reason

        assert asyncio.run(run()) == "timeout"

    def test_receive_data_futura_levanta_disconnected_de_inmediato(self):
        source, *_ = _make_source()

        async def run():
            await source.mark_disconnected("clean_close")
            with pytest.raises(ProxyStreamDisconnected) as exc_info:
                await source.receive_data()
            return exc_info.value.reason

        assert asyncio.run(run()) == "clean_close"

    def test_mensaje_encolado_antes_de_desconectar_se_entrega(self):
        source, *_ = _make_source()

        async def run():
            await source.enqueue_data("a")
            result = await source.receive_data()
            await source.mark_disconnected("timeout")
            return result

        assert asyncio.run(run()) == "a"

    def test_receive_data_cancelado_propaga_cancelled_error(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data entre en la espera
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        asyncio.run(run())

    def test_mensaje_y_desconexion_simultaneos_no_pierden_el_mensaje(self):
        source, *_ = _make_source()

        async def run():
            task = asyncio.create_task(source.receive_data())
            await asyncio.sleep(0)  # deja que receive_data arranque y quede esperando

            await source.enqueue_data("a")
            await source.mark_disconnected("timeout")

            return await task

        assert asyncio.run(run()) == "a"
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/Api && uv run pytest tests/robot/adapters/test_proxy_stream_source.py -v`
Expected: FAIL con `ImportError: cannot import name 'ProxyStreamDisconnected'`

- [ ] **Step 3: Implementar `mark_disconnected` en `ProxyStreamSource`**

Reemplazar el contenido completo de `services/Api/src/robot/adapters/proxy_stream_source.py`:

```python
import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, override

from ..repositories.robot_connection import StreamSource


class ProxyStreamDisconnected(Exception):
    """La conexión física (WS de la Pi) terminó — `reason` es `"clean_close"` o `"timeout"`."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Physical robot connection ended: {reason}")
        self.reason: str = reason


class ProxyStreamSource(StreamSource):
    def __init__(self, *,
        on_recieve: Callable[[Any], Awaitable[None]],  # pyright: ignore[reportExplicitAny]
        on_disconnect: Callable[[], Awaitable[None]],
        on_accept: Callable[[], Awaitable[None]],
        on_idle_changed: Callable[[bool], Awaitable[None]],
    ):
        self.on_recieve: Callable[[Any], Awaitable[None]] = on_recieve  # pyright: ignore[reportExplicitAny]
        self.on_disconnect: Callable[[], Awaitable[None]] = on_disconnect
        self.on_accept: Callable[[], Awaitable[None]] = on_accept
        self.on_idle_changed_callback: Callable[[bool], Awaitable[None]] = on_idle_changed
        self.queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)  # pyright: ignore[reportExplicitAny]
        self._disconnect_event: asyncio.Event = asyncio.Event()
        self._disconnected_exc: ProxyStreamDisconnected | None = None

    async def enqueue_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.queue.put(data)

    async def clean_queue(self):
        while not self.queue.empty():
            _ = self.queue.get_nowait()

    async def on_idle_changed(self, idle: bool):
        return await self.on_idle_changed_callback(idle)

    async def mark_disconnected(self, reason: str) -> None:
        """Marca la conexión física como muerta.

        Cualquier `receive_data()` pendiente o futuro levanta
        `ProxyStreamDisconnected(reason)`. Idempotente: si ya estaba
        marcada, conserva el motivo original.
        """
        if self._disconnected_exc is None:
            self._disconnected_exc = ProxyStreamDisconnected(reason)
        self._disconnect_event.set()

    @override
    async def accept(self):
        return await self.on_accept()

    @override
    async def disconnect(self):
        return await self.on_disconnect()

    @override
    async def receive_data(self) -> Any:  # pyright: ignore[reportExplicitAny, reportAny]
        if self._disconnected_exc is not None:
            raise self._disconnected_exc

        get_task = asyncio.ensure_future(self.queue.get())
        disconnect_task = asyncio.ensure_future(self._disconnect_event.wait())
        try:
            done, pending = await asyncio.wait(
                {get_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
            )
        except BaseException:
            # Si esta corutina es cancelada mientras espera (ej. TaskGroup
            # cancelando el pipe), no dejar tasks huérfanas ni reemplazar
            # el CancelledError propagante por un UnboundLocalError.
            get_task.cancel()
            disconnect_task.cancel()
            raise
        else:
            for task in pending:
                _ = task.cancel()

        if get_task in done:
            # Un mensaje ya disponible se entrega igual, aunque la
            # desconexión haya llegado en el mismo tick (evita perder el
            # mensaje cuando ambos futures resuelven simultáneamente).
            return get_task.result()  # pyright: ignore[reportAny]

        assert self._disconnected_exc is not None
        raise self._disconnected_exc

    @override
    async def send_data(self, data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        await self.on_recieve(data)
```

Modificar `services/Api/src/robot/adapters/__init__.py` para exportar la nueva excepción:

```python
from .user_stream_source import UserStreamSource as UserStreamSource
from .proxy_stream_source import ProxyStreamSource as ProxyStreamSource
from .proxy_stream_source import ProxyStreamDisconnected as ProxyStreamDisconnected
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/Api && uv run pytest tests/robot/adapters/test_proxy_stream_source.py -v`
Expected: PASS (todos, incluyendo los 12 tests preexistentes + los 3 nuevos)

- [ ] **Step 5: Commit**

```bash
git add services/Api/src/robot/adapters/proxy_stream_source.py services/Api/src/robot/adapters/__init__.py services/Api/tests/robot/adapters/test_proxy_stream_source.py
git commit -m "feat(api): ProxyStreamSource propaga la desconexión física al pipe"
```

---

### Task 3: Api — `UserStreamSource` intercepta pong y expone `send_control`

**Files:**
- Modify: `services/Api/src/robot/adapters/user_stream_source.py`
- Test: `services/Api/tests/robot/adapters/test_user_stream_source.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `UserStreamSource(websocket, *, pong_received: asyncio.Event | None = None)` (el parámetro es opcional y retrocompatible), `UserStreamSource.send_control(data: dict) -> None`. Usado por Task 7 (ipc_user_robot_comunication.py).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar a `services/Api/tests/robot/adapters/test_user_stream_source.py` (después de `import asyncio` ya presente, agregar nada nuevo a los imports — `asyncio` ya está importado):

```python
class TestReceiveDataPong:
    def test_pong_no_se_retorna_como_comando_y_marca_el_evento(self):
        ws = _make_ws()
        ws.receive_text.side_effect = [
            '{"type": "pong"}',
            '{"method": "move_arm"}',
        ]
        pong_received = asyncio.Event()
        source = UserStreamSource(ws, pong_received=pong_received)

        result = asyncio.run(source.receive_data())

        assert result == {"method": "move_arm"}
        assert pong_received.is_set()
        ws.send_json.assert_not_awaited()


class TestSendControl:
    def test_send_control_usa_send_json(self):
        ws = _make_ws()
        source = UserStreamSource(ws)

        asyncio.run(source.send_control({"type": "ping"}))

        ws.send_json.assert_awaited_once_with({"type": "ping"})
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/Api && uv run pytest tests/robot/adapters/test_user_stream_source.py -v`
Expected: FAIL — `TypeError: UserStreamSource.__init__() got an unexpected keyword argument 'pong_received'` y `AttributeError: 'UserStreamSource' object has no attribute 'send_control'`

- [ ] **Step 3: Implementar los cambios en `UserStreamSource`**

Reemplazar el contenido completo de `services/Api/src/robot/adapters/user_stream_source.py`:

```python
import asyncio
import json
import logging
from typing import Any, override

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketState

from ..entities.json_rpc_commands import RRobotCommand
from ..repositories.robot_connection import StreamSource


logger = logging.getLogger(__name__)


class UserStreamSource(StreamSource):
    # TODO: manejar cuestiones relacionadas a la sesión del usuario (ejemplo: expiración)
    # TODO: validación profunda del payload — ampliar más allá de RRobotCommand
    # TODO: verificación del access_token per-sesión
    def __init__(self, websocket: WebSocket, *, pong_received: asyncio.Event | None = None):
        self.websocket: WebSocket = websocket
        self.pong_received: asyncio.Event = pong_received if pong_received is not None else asyncio.Event()
        self._send_lock: asyncio.Lock = asyncio.Lock()

    @override
    async def accept(self):
        if self.websocket.application_state != WebSocketState.CONNECTED:
            return await self.websocket.accept()

    @override
    async def disconnect(self):
        return await self.websocket.close()

    @override
    async def receive_data(self) -> Any:
        while True:
            try:
                text = await self.websocket.receive_text()
                logger.info(f"Received text from user: {text}")
                data = json.loads(text)
                if isinstance(data, dict) and data.get("type") == "pong":
                    self.pong_received.set()
                    continue
                command = RRobotCommand.model_validate(data)
                return command.model_dump(mode="python")
            except ValidationError as e:
                logger.error(f"Payload validation error: {e}")
                async with self._send_lock:
                    await self.websocket.send_json({
                        "status": "error",
                        "message": f"Invalid payload: {e.errors()}"
                    })
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                async with self._send_lock:
                    await self.websocket.send_json({
                        "status": "error",
                        "message": f"Invalid JSON: {e}"
                    })

    @override
    async def send_data(self, data: Any) -> None:  # pyright: ignore[reportAny, reportExplicitAny]
        async with self._send_lock:
            await self.websocket.send_json(data)

    async def send_control(self, data: dict) -> None:
        """Envía un frame de control (ej. heartbeat ping) usando el mismo
        lock que `send_data`, para no intercalar escrituras concurrentes
        sobre el mismo WebSocket físico.
        """
        async with self._send_lock:
            await self.websocket.send_json(data)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/Api && uv run pytest tests/robot/adapters/test_user_stream_source.py -v`
Expected: PASS (todos, incluyendo los 8 tests preexistentes + los 2 nuevos)

- [ ] **Step 5: Commit**

```bash
git add services/Api/src/robot/adapters/user_stream_source.py services/Api/tests/robot/adapters/test_user_stream_source.py
git commit -m "feat(api): UserStreamSource intercepta pong y expone send_control"
```

---

### Task 4: Api — `RobotConnectionRepository`: slot de espera para reconexión

**Files:**
- Modify: `services/Api/src/robot/repositories/robot_connection.py`
- Test: `services/Api/tests/robot/repositories/test_robot_connection.py`

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `RobotConnectionRepository.discardDeadRobotConnection(robot: Robot | str) -> None`, `RobotConnectionRepository.wait_for_robot_reconnect(robot_id: str, timeout: float) -> RobotConnection | None`. Usados por Task 6 (m2m.py) y Task 7/5 (pipe) respectivamente.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `services/Api/tests/robot/repositories/test_robot_connection.py`:

```python
class TestDiscardDeadRobotConnection:
    def test_remueve_del_repo_sin_tocar_el_pipe(self, repo):
        user = _make_user()
        robot = _make_robot()
        user_conn = repo.addUserConnection(user, _make_source())
        robot_conn = repo.addRobotConnection(robot, _make_source())
        pipe = repo.addUserXRobotConnection(user_conn, robot_conn)
        pipe._tasks.append(MagicMock())  # simular pipe conectado

        repo.discardDeadRobotConnection(robot)

        assert repo.getRobotConnection(robot) is None
        # el pipe NO se tocó: sigue "conectado" (el propio pipe maneja su espera)
        assert pipe.connected is True

    def test_sobre_robot_inexistente_es_noop(self, repo):
        robot = _make_robot()
        repo.discardDeadRobotConnection(robot)  # no debe lanzar
        assert repo.getRobotConnection(robot) is None


class TestWaitForRobotReconnect:
    def test_retorna_none_si_no_reconecta_a_tiempo(self, repo):
        robot = _make_robot()

        async def run():
            return await repo.wait_for_robot_reconnect(str(robot.id), timeout=0.02)

        assert asyncio.run(run()) is None

    def test_retorna_la_nueva_conexion_si_reconecta_a_tiempo(self, repo):
        robot = _make_robot()

        async def run():
            async def _reconnect_later():
                await asyncio.sleep(0.01)
                repo.addRobotConnection(robot, _make_source())

            waiter = asyncio.create_task(repo.wait_for_robot_reconnect(str(robot.id), timeout=1.0))
            reconnector = asyncio.create_task(_reconnect_later())
            result = await waiter
            await reconnector
            return result

        result = asyncio.run(run())
        assert result is repo.getRobotConnection(robot)
```

Agregar `import asyncio` al inicio del archivo de test (junto a los imports existentes `from unittest.mock import MagicMock`, etc.).

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_robot_connection.py -v`
Expected: FAIL con `AttributeError: 'RobotConnectionRepository' object has no attribute 'discardDeadRobotConnection'`

- [ ] **Step 3: Implementar los cambios en `RobotConnectionRepository`**

En `services/Api/src/robot/repositories/robot_connection.py`, agregar `import asyncio` al inicio (junto a los imports existentes):

```python
from typing import Annotated
from fastapi import Depends
import asyncio
import functools
```

Modificar `__init__` para agregar el diccionario de esperas:

```python
    def __init__(self):
        self._robots: dict[str, RobotConnection] = {}
        self._users: dict[str, UserConnection] = {}
        self._users_x_robot: list[UsersXRobotMapType] = []
        self._robot_reconnect_waiters: dict[str, asyncio.Event] = {}
```

Modificar `addRobotConnection` para notificar a quien esté esperando:

```python
    def addRobotConnection(self, robot: Robot, streamSource: StreamSource) -> RobotConnection:
        if str(robot.id) in self._robots:
            raise ValueError("Robot already connected")

        connection = RobotConnection(streamSource, robot)
        self._robots[str(robot.id)] = connection

        if (event := self._robot_reconnect_waiters.get(str(robot.id))) is not None:
            event.set()

        return connection
```

Agregar los dos métodos nuevos (después de `discardRobotConnection`):

```python
    def discardDeadRobotConnection(self, robot: Robot | str) -> None:
        """Remueve del registro una conexión de robot muerta por timeout
        de heartbeat, sin tocar el pipe usuario↔robot (a diferencia de
        `discardRobotConnection`). El pipe, si existe, maneja su propio
        ciclo de espera/reconexión vía `wait_for_robot_reconnect`.
        """
        if isinstance(robot, Robot):
            robot = str(robot.id)

        _ = self._robots.pop(robot, None)

    async def wait_for_robot_reconnect(self, robot_id: str, timeout: float) -> RobotConnection | None:
        """Espera hasta `timeout` segundos a que un robot se re-registre.

        Retorna la nueva `RobotConnection` si se re-registró a tiempo,
        o `None` si se agotó el timeout sin que el robot reconecte.

        Asume a lo sumo un llamador esperando por `robot_id` a la vez: el
        `asyncio.Event` se comparte por robot_id y el `finally` lo elimina
        incondicionalmente al salir, así que dos esperas concurrentes sobre
        el mismo robot_id perderían la notificación para quien no fue el
        primero en salir (timeout o éxito). Esto no ocurre en la práctica
        porque `addUserXRobotConnection` ya impone como mucho un pipe activo
        por robot (lanza `RobotInUseError` si no) — no es solo una
        convención, hay una invariante real del repositorio detrás.
        """
        event = self._robot_reconnect_waiters.setdefault(robot_id, asyncio.Event())
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            _ = self._robot_reconnect_waiters.pop(robot_id, None)

        return self.getRobotConnection(robot_id)
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_robot_connection.py -v`
Expected: PASS (todos, incluyendo los preexistentes + los 4 nuevos)

- [ ] **Step 5: Commit**

```bash
git add services/Api/src/robot/repositories/robot_connection.py services/Api/tests/robot/repositories/test_robot_connection.py
git commit -m "feat(api): RobotConnectionRepository soporta espera de reconexión del robot"
```

---

### Task 5: Api — el pipe (`UsersXRobotMapType`) sobrevive a una caída del robot

**Files:**
- Modify: `services/Api/src/robot/repositories/stream_entities.py`
- Test: `services/Api/tests/robot/repositories/test_stream_entities.py` (nuevo)

**Interfaces:**
- Consumes: ninguna dependencia directa de Tasks 1-4 en el código de producción (el callback `wait_for_robot_reconnect` se pasa como parámetro, agnóstico de dónde venga — en Task 7 será `RobotConnectionRepository.wait_for_robot_reconnect` de Task 4).
- Produces: `UsersXRobotMapType.connect(*, wait_for_robot_reconnect: Callable[[str, float], Awaitable[RobotConnection | None]], reconnect_timeout: float = 120.0) -> None` (firma nueva, antes era `connect(self)` sin parámetros). Usado por Task 7.

**Nota de diseño para quien implemente:** hoy, si el lado robot del pipe (`self.robot.connect()`) falla dentro del mismo `asyncio.TaskGroup` que el lado usuario, `TaskGroup` cancela automáticamente la tarea del usuario también — y `UserConnection._on_disconnect()` cierra el WebSocket físico del usuario en ese cancel. Por eso el reintento de reconexión del robot **no puede** vivir en un TaskGroup que se recrea desde cero en cada caída (eso cancelaría al usuario de rebote). La solución: un único supervisor de robot, que vive en una sola tarea del TaskGroup exterior y reintenta `self.robot.connect()` puertas adentro, sin nunca hacer que el TaskGroup exterior termine salvo que se agote el tiempo de espera.

- [ ] **Step 1: Escribir el test que falla**

Crear `services/Api/tests/robot/repositories/test_stream_entities.py`:

```python
import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.robot.repositories.stream_entities import (
    RobotConnection,
    RobotSideClosed,
    UserConnection,
    UsersXRobotMapType,
)


class _FakeSource:
    """Doble de StreamSource controlable a mano: permite simular una
    caída física llamando a `die()`, sin depender de ProxyStreamSource."""

    def __init__(self):
        self.disconnected = False
        self.sent = []
        self._recv_queue = asyncio.Queue()
        self._die_event = asyncio.Event()

    async def accept(self):
        return None

    async def disconnect(self):
        self.disconnected = True

    async def receive_data(self):
        get_task = asyncio.ensure_future(self._recv_queue.get())
        die_task = asyncio.ensure_future(self._die_event.wait())
        done, pending = await asyncio.wait(
            {get_task, die_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        if die_task in done:
            raise RuntimeError("conexión física perdida")
        return get_task.result()

    async def send_data(self, data):
        self.sent.append(data)

    def die(self):
        self._die_event.set()


def _make_robot_conn():
    robot = type("FakeRobot", (), {})()
    robot.id = uuid4()
    return RobotConnection(_FakeSource(), robot), robot


def _make_user_conn():
    user = type("FakeUser", (), {})()
    user.id = uuid4()
    return UserConnection(_FakeSource(), user)


class TestRobotReconnectFlow:
    def test_robot_reconecta_dentro_del_timeout_y_el_pipe_sigue(self):
        user_conn = _make_user_conn()
        robot_conn, robot = _make_robot_conn()
        new_robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock(return_value=new_robot_conn)
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(
                    wait_for_robot_reconnect=wait_for_robot_reconnect,
                    reconnect_timeout=5.0,
                )
            )
            await asyncio.sleep(0)
            robot_conn.ws.die()
            await asyncio.sleep(0.01)

            assert pipe.robot is new_robot_conn
            assert {
                "status": "robot_disconnected",
                "message": "robot desconectado, reconectando...",
            } in user_conn.ws.sent
            assert {"status": "robot_reconnected"} in user_conn.ws.sent
            # el usuario nunca se desconectó durante la espera
            assert user_conn.ws.disconnected is False

            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, BaseExceptionGroup):
                pass

        asyncio.run(run())
        wait_for_robot_reconnect.assert_awaited_once_with(str(robot.id), 5.0)

    def test_robot_no_reconecta_a_tiempo_cierra_todo_el_pipe(self):
        user_conn = _make_user_conn()
        robot_conn, robot = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock(return_value=None)
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(
                    wait_for_robot_reconnect=wait_for_robot_reconnect,
                    reconnect_timeout=0.01,
                )
            )
            await asyncio.sleep(0)
            robot_conn.ws.die()
            with pytest.raises(BaseExceptionGroup) as exc_info:
                await task
            return exc_info.value

        eg = asyncio.run(run())
        assert any(isinstance(e, RobotSideClosed) for e in eg.exceptions)
        assert {
            "status": "robot_unavailable",
            "message": "el robot no reconectó a tiempo",
        } in user_conn.ws.sent

    def test_disconnect_cancela_ambos_lados_sin_esperar_reconexion(self):
        user_conn = _make_user_conn()
        robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock()
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(wait_for_robot_reconnect=wait_for_robot_reconnect)
            )
            # Dos sleeps: create_task solo agenda el primer __step (no lo
            # corre). Con un solo sleep(0), las tareas hijas todavía no
            # arrancaron su cuerpo — cancelarlas ahí salta su try/finally
            # de cleanup entero (ws.disconnect() nunca se llama). El
            # segundo sleep(0) les da su primer turno real de ejecución.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            assert pipe.connected is True

            pipe.disconnect()

            with pytest.raises((asyncio.CancelledError, BaseExceptionGroup)):
                await task

            assert user_conn.ws.disconnected is True

        asyncio.run(run())
        wait_for_robot_reconnect.assert_not_called()

    def test_disconnect_cancela_tambien_tareas_extra_registradas(self):
        user_conn = _make_user_conn()
        robot_conn, _ = _make_robot_conn()
        wait_for_robot_reconnect = AsyncMock()
        pipe = UsersXRobotMapType(user=user_conn, robot=robot_conn)

        async def run():
            task = asyncio.create_task(
                pipe.connect(wait_for_robot_reconnect=wait_for_robot_reconnect)
            )
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            async def _forever():
                while True:
                    await asyncio.sleep(3600)

            extra_task = asyncio.create_task(_forever())
            pipe.register_extra_task(extra_task)

            pipe.disconnect()

            with pytest.raises((asyncio.CancelledError, BaseExceptionGroup)):
                await task

            assert extra_task.cancelled() or extra_task.done()

        asyncio.run(run())
```

Este test cubre un hallazgo posterior de Task 7 (ver esa sección): `disconnect()` necesita poder cancelar tareas externas (ej. el watchdog de heartbeat del usuario) registradas por el caller, no solo las internas del pipe — de lo contrario esas tareas sobreviven contra un WebSocket ya cerrado y terminan lanzando una excepción no relacionada más adelante.

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_stream_entities.py -v`
Expected: FAIL con `TypeError: UsersXRobotMapType.connect() missing 1 required keyword-only argument: 'wait_for_robot_reconnect'` (o error de tipo similar, ya que `connect()` hoy no acepta ese parámetro)

- [ ] **Step 3: Implementar la reconexión en `UsersXRobotMapType`**

En `services/Api/src/robot/repositories/stream_entities.py`, cambiar el import de `typing` para agregar `Awaitable`:

```python
from typing import Any, Awaitable, Callable, Coroutine, Never, Protocol, final, override
```

Agregar la constante de timeout después de `logger = logging.getLogger(__name__)`:

```python
_ROBOT_RECONNECT_WAIT_SECONDS: float = 120.0
```

Actualizar el docstring de `RobotSideClosed` (era `"""La conexión del lado robot del pipe terminó (cierre normal o error)."""`):

```python
class RobotSideClosed(Exception):
    """La conexión del lado robot del pipe terminó sin reconectar a tiempo."""
```

Reemplazar la clase `UsersXRobotMapType` completa (deja intactas `StreamSource`, `StreamConnection`, `RobotConnection`, `UserConnection` arriba en el archivo):

```python
@final
class UsersXRobotMapType:
    def __init__(self, user: UserConnection, robot: RobotConnection):
        self.user = user
        self.robot = robot
        self._tasks: list[asyncio.Task[Never]] = []
        self._disconnectables: list[RemoveListener] = []
        # Tarea que corre `connect()` (el "padre" del TaskGroup interno).
        # Necesaria porque `disconnect()` puede invocarse desde otra tarea
        # mientras `connect()` sigue corriendo: cancelar directamente las
        # tareas hijas (`self._tasks`) no alcanza, ya que `TaskGroup`
        # ignora cancelaciones externas de sus hijos si la propia tarea
        # padre nunca fue cancelada (ver `asyncio.taskgroups._on_task_done`,
        # que hace `if task.cancelled(): return` sin registrar error ni
        # abortar al resto) — el grupo terminaría sin excepción alguna.
        # Cancelar la tarea padre sí dispara el camino normal de
        # cancelación de `TaskGroup._aexit`.
        self._connect_task: asyncio.Task[None] | None = None
        self._extra_tasks: list[asyncio.Task[Any]] = []

    @property
    def connected(self) -> bool:
        return len(self._tasks) > 0

    def register_extra_task(self, task: asyncio.Task[Any]) -> None:
        """Registra una tarea externa (ej. el watchdog de heartbeat del
        usuario en ipc_user_robot_comunication.py) para que `disconnect()`
        la cancele junto con el pipe.

        Necesario porque un `disconnect()` externo cancela `_connect_task`
        (la tarea que corre `connect()`), pero no tiene forma de conocer
        otras tareas hermanas que el caller haya lanzado en su propio
        TaskGroup (ej. un heartbeat) — sin este registro, esas tareas
        seguirían corriendo contra un WebSocket ya cerrado tras el
        disconnect, y terminarían lanzando una excepción no relacionada
        (ej. al intentar escribir al socket) en vez de terminar
        silenciosamente junto con el resto del pipe.
        """
        self._extra_tasks.append(task)

    def _bind_robot_listeners(self) -> None:
        for remove in self._disconnectables:
            remove()
        self._disconnectables = [
            self.user.on(self.robot.send),
            self.robot.on(self.user.send),
        ]

    async def _supervise_robot(
        self,
        wait_for_robot_reconnect: Callable[[str, float], Awaitable[RobotConnection | None]],
        reconnect_timeout: float,
    ) -> Never:
        """Corre `self.robot.connect()` en loop, sobreviviendo a caídas.

        Si el robot se cae, notifica al usuario y espera a que
        `wait_for_robot_reconnect` devuelva una nueva `RobotConnection`.
        Si llega a tiempo, se re-vincula (`self.robot = new_robot`) y
        se reintenta. Si se agota el timeout, levanta `RobotSideClosed`
        — recién ahí termina también el lado usuario (vía TaskGroup).
        """
        while True:
            try:
                await self.robot.connect()
            except Exception as e:
                robot_id = str(self.robot.robot.id)

                await self.user.send({
                    "status": "robot_disconnected",
                    "message": "robot desconectado, reconectando...",
                })

                new_robot = await wait_for_robot_reconnect(robot_id, reconnect_timeout)

                if new_robot is None:
                    await self.user.send({
                        "status": "robot_unavailable",
                        "message": "el robot no reconectó a tiempo",
                    })
                    raise RobotSideClosed() from e

                self.robot = new_robot
                self._bind_robot_listeners()
                await self.user.send({"status": "robot_reconnected"})
                continue

            # `RobotConnection.connect()` está anotado `Never`: no debería
            # retornar. Si algún día lo hace, no dejamos el supervisor
            # colgado en silencio.
            raise AssertionError("unreachable: RobotConnection.connect() no debería retornar")

    async def connect(
        self,
        *,
        wait_for_robot_reconnect: Callable[[str, float], Awaitable[RobotConnection | None]],
        reconnect_timeout: float = _ROBOT_RECONNECT_WAIT_SECONDS,
    ) -> None:
        self._bind_robot_listeners()
        self._connect_task = asyncio.current_task()

        try:
            async with asyncio.TaskGroup() as tg:
                self._tasks = [
                    tg.create_task(_wrap_side(self.user.connect(), UserSideClosed)),
                    tg.create_task(self._supervise_robot(wait_for_robot_reconnect, reconnect_timeout)),
                ]
        finally:
            self._connect_task = None

    def disconnect(self):
        if self._connect_task is not None:
            _ = self._connect_task.cancel()

        for task in self._tasks:
            _ = task.cancel()

        for task in self._extra_tasks:
            _ = task.cancel()

        for func in self._disconnectables:
            try:
                func()
            except Exception:
                logger.warning("Listener cleanup raised", exc_info=True)

        self._tasks = []
        self._disconnectables = []
        self._extra_tasks = []
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `cd services/Api && uv run pytest tests/robot/repositories/test_stream_entities.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Correr toda la suite de Api para descartar regresiones**

Run: `cd services/Api && uv run pytest -v`
Expected: PASS (todos los tests, incluyendo `tests/robot/repositories/test_robot_connection.py` cuyo helper `_make_source()` usa `MagicMock()` — verificar que `test_discard_user_con_pipe_y_disconnect_true_limpia_cascada` sigue pasando, ya que ejercita `UsersXRobotMapType.disconnect()` sin invocar `connect()`)

- [ ] **Step 6: Commit**

```bash
git add services/Api/src/robot/repositories/stream_entities.py services/Api/tests/robot/repositories/test_stream_entities.py
git commit -m "feat(api): el pipe usuario-robot sobrevive a una caida y reconexion del robot"
```

---

### Task 6: Api — `m2m.py` distingue cierre limpio de timeout de heartbeat

**Files:**
- Modify: `services/Api/src/robot/routes/m2m.py`

**Interfaces:**
- Consumes: `run_heartbeat_watchdog`/`HeartbeatTimeoutError` (Task 1), `ProxyStreamSource.mark_disconnected` (Task 2), `RobotConnectionRepository.discardDeadRobotConnection`/`discardRobotConnection` (Task 4, la segunda ya existía).
- Produces: nada consumido por otra tarea (es el punto de entrada de la conexión Pi).

**Nota:** esta tarea es orquestación de ruta (glue code) sobre piezas ya testeadas en Tasks 1, 2 y 4 — sigue la convención del proyecto (`routes: solo orquesta, sin tests unitarios propios`, ver `services/Api/CLAUDE.md`). No hay test automatizado nuevo para este archivo (no hay precedente de `TestClient`/WS testing en el repo); se verifica con el smoke test manual del Step 3.

- [ ] **Step 1: Modificar `m2m.py`**

Reemplazar el contenido completo de `services/Api/src/robot/routes/m2m.py`:

```python
"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

import asyncio
import logging
from typing import Annotated, Any
from uuid import UUID as PythonUUID
from fastapi import APIRouter, Depends, WebSocket
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jwt import ExpiredSignatureError
from pydantic import ValidationError

from ..entities.robot import Robot, RobotStreamAutentication
from ..adapters import ProxyStreamSource
from ..repositories.robot_connection import RobotConnectionRepositoryDep
from ..services.handshake_service import HandshakeService, HandshakeServiceDep
from ..services import (
    RobotServiceDep, RobotRegistrationInput, RobotRegistrationOutput, RobotHandshakeResult, RobotResponse
)
from ..utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog

router = APIRouter(tags=["robots", "m2m"])

security = HTTPBasic()

logger = logging.getLogger(__name__)

@router.post("/register", response_model=RobotRegistrationOutput)
def register_robot(
    robot_service: RobotServiceDep,
    registration: RobotRegistrationInput,
) -> RobotRegistrationOutput:
    robot = robot_service.register_robot(registration)
    return RobotRegistrationOutput(
        external_identifier=PythonUUID(robot.external_identifier),
        status=robot.status,
    )


@router.post("/handshake", response_model=RobotHandshakeResult)
def login(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    handshake_service: Annotated[HandshakeService, Depends(HandshakeService)]
) -> RobotHandshakeResult:
    accessToken, _ = handshake_service.create_access_token_by_basic_credentials(credentials)
    return RobotHandshakeResult(
        access_token=accessToken,
    )

@router.websocket('/connect')
async def robot_connection(
    websocket: WebSocket,
    robot_connection_repository: RobotConnectionRepositoryDep,
    robot_handshake_service: HandshakeServiceDep
):
    await websocket.accept()

    # == validate

    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "send_credentials",
        "params": [],
        "id": 1
    })

    robot: Robot | None

    try:
        access_bare_data: dict[str, Any] = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny, reportExplicitAny]
        access_data = RobotStreamAutentication.model_validate(access_bare_data)
        robot= robot_handshake_service.get_robot_by_token(access_data.token)
    except ExpiredSignatureError as e:
        logger.error(e)
        await websocket.send_json({
            "status": "error",
            "message": "Token expired"
        })
        await websocket.close()
        return
    except Exception as e:
        logger.error(e)
        await websocket.send_json({
            "status": "error",
            "message": "Error validating token"
        })
        await websocket.close()
        return


    if robot is None:
        await websocket.send_json({
            "status": "error",
            "message": "Robot not found"
        })
        await websocket.close()
        return
    else:
        await websocket.send_json({
            "status": "success auth",
        })

    # ====

    # Flag activado cuando hay un usuario consumiendo el pipe (gated por
    # on_idle_changed desde RobotConnection). Sin consumidor → no se
    # enqueuan mensajes para evitar llenar la queue sin lectores.
    pipe_active: bool = False

    async def set_pipe_active(idle: bool) -> None:
        nonlocal pipe_active
        pipe_active = not idle
        logger.info("Pipe active: %s", pipe_active)

    async def noop_async() -> None:
        return None

    send_lock = asyncio.Lock()

    async def _send_json_locked(data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        async with send_lock:
            await websocket.send_json(data)

    streamSource = ProxyStreamSource(
        on_recieve=_send_json_locked,
        on_accept=noop_async,
        on_disconnect=noop_async,
        on_idle_changed=set_pipe_active,
    )

    _ = robot_connection_repository.addRobotConnection(robot, streamSource)

    pong_received = asyncio.Event()
    pong_received.set()

    async def _send_ping() -> None:
        await _send_json_locked({"type": "ping"})

    async def _receive_loop() -> None:
        # No usamos `websocket.iter_json()`: internamente atrapa
        # `WebSocketDisconnect` y termina el generador en silencio, sin
        # propagar nada. Eso hace que, ante cualquier cierre del socket
        # (voluntario o no), este loop termine "exitosamente" y la única
        # señal de corte termine siendo, siempre, el timeout del
        # heartbeat — nunca `except* Exception` (clean_close). Llamando a
        # `receive_json()` directo, `WebSocketDisconnect` se propaga y
        # permite distinguir el cierre limpio del timeout, tal como
        # corresponde.
        while True:
            message: Any = await websocket.receive_json()  # pyright: ignore[reportAny]
            logger.info("Message received: %s", message)
            if isinstance(message, dict) and message.get("type") == "pong":
                pong_received.set()
                continue
            if not pipe_active:
                continue
            try:
                validated = RobotResponse.model_validate(message)
            except ValidationError:
                logger.warning("Mensaje del robot mal formado, descartando: %s", message)
                continue
            await streamSource.enqueue_data(validated.model_dump(mode="python"))

    disconnect_reason = "clean_close"
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_receive_loop())
            tg.create_task(run_heartbeat_watchdog(_send_ping, pong_received))
    except* HeartbeatTimeoutError:
        disconnect_reason = "timeout"
        logger.warning("Sin heartbeat del robot %s, cerrando conexión", robot.id)
    except* Exception:
        disconnect_reason = "clean_close"
        logger.info("Conexión del robot %s cerrada limpiamente", robot.id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

        await streamSource.mark_disconnected(disconnect_reason)

        if disconnect_reason == "timeout":
            robot_connection_repository.discardDeadRobotConnection(robot)
        else:
            robot_connection_repository.discardRobotConnection(robot, discardPipeddConnections=True)
```

- [ ] **Step 2: Correr toda la suite de Api para descartar regresiones**

Run: `cd services/Api && uv run pytest -v`
Expected: PASS (todos los tests existentes — este archivo no tiene tests unitarios propios, así que ningún test nuevo debería aparecer, pero ninguno de los existentes debe romperse)

- [ ] **Step 3: Smoke test manual en modo demo**

Con la Api y una Pi en modo mock corriendo (`MOCK_ROBOT=1`, ver sección "Ejecutar la RaspberryPi" del `CLAUDE.md` raíz):

1. Arrancar la Api (`cd services/Api && make up_dev`) y la Pi (`cd services/RaspberryPi && uv run python -m controller`).
2. Verificar en los logs de la Api que, tras la conexión, no aparece ningún error al recibir pings (todavía no hay pong porque la Pi no los responde hasta Task 8 — es esperable ver `Sin heartbeat del robot..., cerrando conexión` en el log de la Api pasados ~25s; esto es el comportamiento correcto hasta que se complete Task 8).
3. Matar el proceso de la Pi (Ctrl+C) y verificar en el log de la Api que aparece `Conexión del robot ... cerrada limpiamente` y que un segundo intento de conexión del mismo `external_identifier` (reiniciar la Pi) no lanza `ValueError: Robot already connected`.

- [ ] **Step 4: Commit**

```bash
git add services/Api/src/robot/routes/m2m.py
git commit -m "feat(api): m2m.py detecta caidas silenciosas via heartbeat y limpia el estado"
```

---

### Task 7: Api — `ipc_user_robot_comunication.py` maneja `RobotSideClosed` y heartbeat de usuario

**Files:**
- Modify: `services/Api/src/robot/services/ipc_user_robot_comunication.py`

**Interfaces:**
- Consumes: `run_heartbeat_watchdog`/`HeartbeatTimeoutError` (Task 1), `UserStreamSource(websocket, pong_received=...)`/`.send_control` (Task 3), `UsersXRobotMapType.connect(wait_for_robot_reconnect=...)` (Task 5), `RobotConnectionRepository.wait_for_robot_reconnect` (Task 4), `RobotSideClosed` (Task 5, ya existía el símbolo pero cambia su significado).

**Nota:** al igual que Task 6, esta tarea es orquestación de servicio sobre piezas ya testeadas — el archivo de test existente (`tests/robot/services/test_ipc_user_robot_comunication.py`) solo cubre `_validate_user_session` (no `connect_ws`), precedente que se mantiene: no se agrega test nuevo para `connect_ws` en esta tarea, se verifica con el smoke test manual del Step 3.

- [ ] **Step 1: Modificar `ipc_user_robot_comunication.py`**

Reemplazar el contenido completo de `services/Api/src/robot/services/ipc_user_robot_comunication.py`:

```python
"""Comunicación usuario ↔ robot vía WebSocket directo.

El usuario se conecta por WebSocket a la API, se autentica, y envía
comandos JSON-RPC. La API enruta cada mensaje hacia el WebSocket de la
Pi del robot a través del pipe `UsersXRobotMapType` (ver
`RobotConnection` / `UserConnection`) y devuelve las respuestas por el
mismo camino.
"""

import asyncio
import logging
from typing import Annotated, final
import functools

from fastapi import Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..entities.errors import (
    JSONRPC_INTERNAL_ERROR,
    SerializableException,
    UserValidationTimeoutException,
    serialise_as_jsonrpc_error,
)
from ..entities.json_rpc_commands import UserWsAuthentication
from ..utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog
from .robot_service import RobotServiceDep, RobotService
from .access_validator import AccessValidator, UserRobotAccessSession
from ..entities import Robot
from ..repositories.robot_connection import RobotConnectionRepository, RobotConnectionRepositoryDep
from ..repositories.stream_entities import RobotSideClosed, UserSideClosed
from ..adapters import UserStreamSource
from ...auth.entities import User
from ...auth.services import UserService, UserServiceDep


logger = logging.getLogger(__name__)

class RobotConnectionNotFound(Exception):
    def __init__(self, robot: Robot) -> None:
        super().__init__("Robot is Disconnected")
        self.robot = robot



@final
class UserToRobotComunication:
    """Gestiona la comunicación WebSocket de un usuario con su robot a través de la API."""

    def __init__(self,
        robot_service: RobotService,
        access_validator: AccessValidator,
        robot_connection_repository: RobotConnectionRepository,
        user_service: UserService,
    ):
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.robot_connection_repository = robot_connection_repository
        self.user_service = user_service

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        user = None
        try:
            logger.info("validating user")
            user, robot = await self._validate_user_session(websocket)

            logger.info("establishing user connection")
            pong_received = asyncio.Event()
            pong_received.set()
            userStreamSource = UserStreamSource(websocket, pong_received=pong_received)
            userConnection = self.robot_connection_repository.addUserConnection(
                user,
                userStreamSource
            )

            logger.info("obtaining robot connection")
            robotConnection = self.robot_connection_repository.getRobotConnection(robot)

            if robotConnection is None:
                raise RobotConnectionNotFound(robot)

            logger.info("creating User-robot comunication pipe")
            bidirectionalPipe = self.robot_connection_repository.addUserXRobotConnection(userConnection, robotConnection)

            async def _send_ping() -> None:
                await userStreamSource.send_control({"type": "ping"})

            async def _watch_heartbeat() -> None:
                try:
                    await run_heartbeat_watchdog(_send_ping, pong_received)
                except HeartbeatTimeoutError:
                    logger.warning("Heartbeat del usuario expiró, cerrando conexión")
                    await websocket.close()

            logger.info("connecting pipe")
            try:
                async with asyncio.TaskGroup() as tg:
                    # Se registra en el pipe para que disconnect() (ej. el
                    # camino clean_close de m2m.py) también la cancele —
                    # de lo contrario sobrevive contra un WS ya cerrado y
                    # termina lanzando una excepción no relacionada en su
                    # próximo ciclo de ping.
                    heartbeat_task = tg.create_task(_watch_heartbeat())
                    bidirectionalPipe.register_extra_task(heartbeat_task)
                    tg.create_task(bidirectionalPipe.connect(
                        wait_for_robot_reconnect=self.robot_connection_repository.wait_for_robot_reconnect,
                    ))
            except* UserSideClosed:
                logger.info("user closed websocket, ending session")
            except* RobotSideClosed:
                logger.info("robot no reconectó a tiempo, cerrando sesión de usuario")

        except WebSocketDisconnect:
            logger.info("Client disconnected")
        except SerializableException as e:
            logger.warning("SerializableException: %s", e.to_dict())
            await websocket.send_json(
                serialise_as_jsonrpc_error(e, message_id=None, code=JSONRPC_INTERNAL_ERROR)
            )
            await websocket.close()
        except ExceptionGroup as eg:
            logger.error("connect user ws error:")
            for exc in eg.exceptions:
                logger.error(f"TaskGroup sub-exception: {exc}", exc_info=exc)
            await websocket.send_json({"status": "error", "message": "Internal Server Error"})
            await websocket.close()
        except RobotConnectionNotFound as e:
            await websocket.send_json({"status": "error", "message": "Robot is Disconnected"})
            await websocket.close()
        except Exception as e:
            logger.error(f"Exception {e}", exc_info=e)
            await websocket.send_json({"status": "error", "message": "Internal Server Error"})
            await websocket.close()
        finally:
            if user is not None:
                self.robot_connection_repository.discardUserConnection(user, discardPipeddConnections=True)

    async def _validate_user_session(self, websocket: WebSocket) -> tuple[User, Robot]:
        try:

            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny]

            entity = UserWsAuthentication.model_validate(result)

            user = self.user_service.get_user_by_token(entity.token)
            robot = self.robot_service.get_robot_by_id(entity.robot_id)

            if user is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            if robot is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            self.access_validator.validate_grant_access(
                entity.token,
                entity.robot_id,
                UserRobotAccessSession(user.usr_name),
            )

            await websocket.send_json({"message": "success auth"})

            return user, robot

        except asyncio.TimeoutError as e:
            logger.error(e)
            raise UserValidationTimeoutException() from e


@functools.cache
def create_user_robot_communication(
        robot_service: RobotServiceDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
        robot_connection_repository: RobotConnectionRepositoryDep,
        user_service: UserServiceDep
) -> UserToRobotComunication:
    return UserToRobotComunication(
        robot_service,
        access_validator,
        robot_connection_repository,
        user_service
    )


RobotIPCDep = Annotated[UserToRobotComunication, Depends(create_user_robot_communication)]
```

- [ ] **Step 2: Correr toda la suite de Api para descartar regresiones**

Run: `cd services/Api && uv run pytest -v`
Expected: PASS (incluyendo `tests/robot/services/test_ipc_user_robot_comunication.py`, que sigue ejercitando solo `_validate_user_session` y no se ve afectado por estos cambios)

- [ ] **Step 3: Smoke test manual en modo demo**

Con la Api y la Pi corriendo (mock), y un usuario aprobado con acceso al robot:

1. Conectar un usuario al robot desde el WebClient (o un cliente WS manual) y verificar que el estado pasa a `connected`.
2. Matar el proceso de la Pi (Ctrl+C) y verificar que el usuario recibe `{"status": "robot_disconnected", ...}` y la conexión del usuario **no se cierra** (el WS sigue abierto).
3. Reiniciar la Pi dentro de los 120s y verificar que el usuario recibe `{"status": "robot_reconnected"}` sin haber tenido que reconectar su propio WS.
4. Repetir el punto 2 pero esperar más de 120s sin reiniciar la Pi: verificar que el usuario recibe `{"status": "robot_unavailable", ...}` y luego su WS se cierra.

- [ ] **Step 4: Commit**

```bash
git add services/Api/src/robot/services/ipc_user_robot_comunication.py
git commit -m "feat(api): sesion de usuario sobrevive a una caida de la Pi via heartbeat"
```

---

### Task 8: RaspberryPi — `WsStrategy` responde heartbeat y detecta Api caída

**Files:**
- Modify: `services/RaspberryPi/controller/strategy/remote/ws_strategy.py`
- Test: `services/RaspberryPi/controller/tests/test_ws_strategy.py` (nuevo)

**Interfaces:**
- Consumes: nada nuevo (no depende de los cambios en Api).
- Produces: comportamiento nuevo en `WsStrategy.receive()`, sin cambiar su firma pública ni la de `send()`/`start()`/`stop()`.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `services/RaspberryPi/controller/tests/test_ws_strategy.py`:

```python
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from controller.strategy.remote import ws_strategy
from controller.strategy.remote.ws_strategy import WsStrategy


class _FakeConnection:
    """Doble de ClientConnection: entrega mensajes de una lista y luego
    se queda "colgada" (simula que no llega nada más, forzando el
    timeout del heartbeat si aplica)."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.sent = []
        self.closed = False

    async def recv(self):
        if not self._messages:
            await asyncio.sleep(3600)
        return self._messages.pop(0)

    async def send(self, data):
        self.sent.append(data)

    async def close(self):
        self.closed = True


def _make_strategy():
    return WsStrategy(
        server_url="http://api.example/m2m/robot/",
        metadata_file="/tmp/unused-robot-metadata.json",
    )


class TestPingPong:
    def test_ping_se_responde_con_pong_y_no_se_retorna_como_comando(self):
        strategy = _make_strategy()
        strategy._ws = _FakeConnection([
            json.dumps({"type": "ping"}),
            json.dumps({"jsonrpc": "2.0", "method": "move_arm", "params": {}, "id": 1}),
        ])

        result = asyncio.run(strategy.receive())

        assert result["method"] == "move_arm"
        assert json.loads(strategy._ws.sent[0]) == {"type": "pong"}


class TestHeartbeatWatchdog:
    def test_sin_ping_de_la_api_fuerza_reconexion(self, monkeypatch):
        monkeypatch.setattr(ws_strategy, "_HEARTBEAT_TIMEOUT_SECONDS", 0.02)
        strategy = _make_strategy()
        strategy._ws = _FakeConnection([])

        reconnected = _FakeConnection([
            json.dumps({"jsonrpc": "2.0", "method": "ping_ok", "params": {}, "id": 2}),
        ])

        async def _fake_reconnect():
            strategy._ws = reconnected

        strategy._reconnect = AsyncMock(side_effect=_fake_reconnect)

        result = asyncio.run(asyncio.wait_for(strategy.receive(), timeout=2.0))

        assert result["method"] == "ping_ok"
        strategy._reconnect.assert_awaited_once()
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `cd services/RaspberryPi && uv run pytest controller/tests/test_ws_strategy.py -v`
Expected: FAIL — el primer test retorna el ping como si fuera un comando (`result["method"]` sería `None` o lanzaría `KeyError`, ya que `_parse_message` hoy no distingue el ping y `parse_command` fallaría su validación silenciosamente devolviendo `None`, haciendo que el loop nunca retorne dentro del timeout del test); el segundo test falla porque no existe `_HEARTBEAT_TIMEOUT_SECONDS` en el módulo

- [ ] **Step 3: Implementar el heartbeat en `WsStrategy`**

Reemplazar el contenido completo de `services/RaspberryPi/controller/strategy/remote/ws_strategy.py`:

```python
"""Strategy remoto: conexión directa a la API via WebSocket.

Gestiona sus propias credenciales (registro + handshake HTTP con la API)
y se conecta al endpoint WS /m2m/robot/connect. Los mensajes son
JSON-RPC 2.0 directo.
"""

import asyncio
import json
import logging
from typing import Any, override

from websockets.asyncio.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosed, InvalidURI

from pydantic import ValidationError

from ..base import Strategy, State
from ...server.server_service import ServerServices, RobotCredentials
from ...json_rpc import parse_command, _error_response

logger = logging.getLogger(__name__)

_MIN_RECONNECT_DELAY = 1.0
_MAX_RECONNECT_DELAY = 30.0
_HEARTBEAT_TIMEOUT_SECONDS = 25.0


class _HeartbeatTimeout(Exception):
    """No llegó un ping de la Api dentro del timeout esperado: se asume conexión muerta."""


def _derive_ws_url(server_url: str) -> str:
    """Deriva la URL del WebSocket a partir de la URL HTTP del servidor.

    http://host/m2m/robot/  → ws://host/m2m/robot/connect
    https://host/m2m/robot/ → wss://host/m2m/robot/connect
    """
    url = server_url.rstrip("/")
    if url.startswith("https://"):
        url = "wss://" + url[len("https://"):]
    elif url.startswith("http://"):
        url = "ws://" + url[len("http://"):]
    return url + "/connect"


class WsStrategy(Strategy):
    """Conecta a la API como strategy remoto via WebSocket directo.

    start() ejecuta registro + handshake HTTP y conecta al WS de la API.
    receive() entrega comandos JSON-RPC recibidos del WS.
    send() envía respuestas/notificaciones JSON-RPC por el WS.
    """

    def __init__(
        self,
        *,
        server_url: str,
        metadata_file: str,
        create_default_metadata: bool = False,
    ):
        self._ws_url: str = _derive_ws_url(server_url)
        self._server_service: ServerServices = ServerServices(
            base_url=server_url,
            metadata_file=metadata_file,
            create_default_config=create_default_metadata,
        )
        self._ws: ClientConnection | None = None
        self._credentials: RobotCredentials | None = None

    @override
    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)

        await self._connect_ws()
        self._state = State.RUNNING
        logger.info("WsStrategy iniciado (ws: %s)", self._ws_url)

    @override
    async def stop(self) -> None:
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._state = State.STOPPED
        logger.info("WsStrategy detenido")

    @override
    async def receive(self) -> Any:
        """Escucha comandos JSON-RPC del WS de la API."""
        delay = _MIN_RECONNECT_DELAY
        last_ping_at = asyncio.get_event_loop().time()

        while True:
            try:
                while True:
                    remaining = _HEARTBEAT_TIMEOUT_SECONDS - (
                        asyncio.get_event_loop().time() - last_ping_at
                    )
                    if remaining <= 0:
                        raise _HeartbeatTimeout()

                    try:
                        raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
                    except asyncio.TimeoutError as e:
                        raise _HeartbeatTimeout() from e

                    delay = _MIN_RECONNECT_DELAY

                    if await self._handle_if_ping(raw):
                        last_ping_at = asyncio.get_event_loop().time()
                        continue

                    msg = self._parse_message(raw)
                    if msg is not None:
                        return msg

            except (ConnectionClosed, _HeartbeatTimeout) as e:
                if isinstance(e, _HeartbeatTimeout):
                    logger.warning(
                        "Sin heartbeat de la Api en %.1fs, forzando reconexión en %.1fs...",
                        _HEARTBEAT_TIMEOUT_SECONDS, delay,
                    )
                    try:
                        await self._ws.close()  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
                    except Exception:
                        pass
                else:
                    logger.warning(
                        "Conexión WS perdida, reconectando en %.1fs...", delay,
                    )

                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RECONNECT_DELAY)
                try:
                    await self._reconnect()
                    last_ping_at = asyncio.get_event_loop().time()
                    logger.info("Reconectado al WS de la API")
                except (OSError, InvalidURI, ConnectionError) as e2:
                    logger.error("Error reconectando: %s", e2)

    @override
    async def send(self, message: Any) -> None:
        """Envía un mensaje JSON-RPC por el WS."""
        try:
            await self._ws.send(json.dumps(message))  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
        except ConnectionClosed:
            logger.warning("No se pudo enviar mensaje (conexión perdida)")

    # --- Internos ---

    def _authenticate(self) -> None:
        """Ejecuta registro + handshake HTTP (sync). Bloquea hasta ser aprobado."""
        self._server_service.load_config()
        if not self._server_service.connect_with_retry():
            raise EnvironmentError("No se pudo establecer conexión con el servidor.")
        self._credentials = self._server_service.credentials

    async def _connect_ws(self) -> None:
        """Conecta al WS de la API y completa el handshake de autenticación."""
        self._ws = await connect(self._ws_url)

        # Recibir challenge del servidor
        challenge_raw = await self._ws.recv()
        challenge = json.loads(challenge_raw)
        if challenge.get("method") != "send_credentials":
            raise ConnectionError(
                f"Challenge inesperado del servidor: {challenge}"
            )

        # Enviar token JWT
        assert self._credentials is not None
        token = self._credentials.access_token.access_token
        await self._ws.send(json.dumps({"token": token}))

        # Esperar confirmación
        result_raw = await self._ws.recv()
        result = json.loads(result_raw)
        if result.get("status") != "success auth":
            raise ConnectionError(
                f"Auth WS fallido: {result}"
            )

        logger.info("Auth WS exitoso")

    async def _reconnect(self) -> None:
        """Re-autentica (JWT puede haber expirado) y reconecta al WS."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._authenticate)
        await self._connect_ws()

    async def _handle_if_ping(self, raw: Any) -> bool:
        """Si `raw` es un ping de heartbeat de la Api, responde el pong.

        Retorna True si `raw` era un ping (ya manejado, no debe
        procesarse como comando), False en caso contrario.
        """
        try:
            data = raw if isinstance(raw, dict) else json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return False

        if not (isinstance(data, dict) and data.get("type") == "ping"):
            return False

        await self._ws.send(json.dumps({"type": "pong"}))  # type: ignore[union-attr]  # pyright: ignore[reportOptionalMemberAccess]
        return True

    def _parse_message(self, raw: Any) -> dict[str, Any] | None:
        """Parsea un mensaje WS como comando JSON-RPC.

        Retorna el comando como dict, o None si no es parseable.
        """
        try:
            data = raw if isinstance(raw, str) else json.dumps(raw)
            command = parse_command(data)
            logger.info("Comando recibido: %s", command.method)
            return command.model_dump(mode="json")

        except ValidationError as e:
            logger.warning("Comando JSON-RPC inválido: %s", e)
            return _error_response(None, -32600, "Comando inválido").model_dump(mode="json")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Mensaje no parseable: %s", e)
            return None
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `cd services/RaspberryPi && uv run pytest controller/tests/test_ws_strategy.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Correr toda la suite de RaspberryPi para descartar regresiones**

Run: `cd services/RaspberryPi && uv run pytest -v`
Expected: PASS (incluyendo `controller/tests/test_ros2.py`, no relacionado con este cambio)

- [ ] **Step 6: Commit**

```bash
git add services/RaspberryPi/controller/strategy/remote/ws_strategy.py services/RaspberryPi/controller/tests/test_ws_strategy.py
git commit -m "feat(raspberrypi): WsStrategy responde heartbeat y detecta caida silenciosa de la Api"
```

---

### Task 9: WebClient — `useRobotSocket` reconecta solo con backoff y heartbeat

**Files:**
- Modify: `services/WebClient/src/composables/useRobotSocket.ts`

**Interfaces:**
- Produces: `useRobotSocket()` retorna, además de lo existente, `robotStatus: Readonly<Ref<RobotAvailability>>`. El tipo `SocketStatus` gana el valor `'reconnecting'`. Usado por Task 10.

**Nota:** no hay infraestructura de test automatizado en `services/WebClient/` (sin vitest, sin `*.test.*` en el repo) — esta tarea se verifica manualmente en el Step 3, no hay pasos de TDD con test runner.

- [ ] **Step 1: Reemplazar `useRobotSocket.ts`**

Reemplazar el contenido completo de `services/WebClient/src/composables/useRobotSocket.ts`:

```typescript
import { readonly, ref } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''

export type SocketStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting' | 'error'
export type RobotState = Record<string, unknown>
export type RobotAvailability = 'robot_disponible' | 'robot_desconectado_reconectando' | 'robot_no_disponible'

interface RobotResponseJSONRPC {
  "jsonrpc": string,
  "method": string,
  "params": Record<string, unknown> | null
}

const isJSONRPC = (data: unknown): data is RobotResponseJSONRPC => {
  if (typeof data !== 'object' || data === null) return false
  return data.hasOwnProperty('jsonrpc')
}

const HEARTBEAT_WATCHDOG_INTERVAL_MS = 1000
const HEARTBEAT_TIMEOUT_MS = 25000
const MIN_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

// La Api (ver stream_entities.py) manda estos nombres de evento en inglés;
// se traducen acá al dominio interno de RobotAvailability (español) que
// consume la UI (Task 10). `robot_reconnected` resuelve de vuelta al
// estado sano (`robot_disponible`), no a un literal propio.
const ROBOT_STATUS_MAP: Record<string, RobotAvailability> = {
  robot_disconnected: 'robot_desconectado_reconectando',
  robot_reconnected: 'robot_disponible',
  robot_unavailable: 'robot_no_disponible',
}

export function useRobotSocket() {
  const status = ref<SocketStatus>('disconnected')
  const robotStatus = ref<RobotAvailability>('robot_disponible')
  const messages = ref<Record<string, unknown>[]>([])
  const error = ref<string | null>(null)
  const robotState = ref<RobotState>({})

  let ws: WebSocket | null = null
  let robotId: string | null = null
  let robotAccessToken: string | null = null
  let manualDisconnect = false
  let authFailed = false
  let reconnectDelayMs = MIN_RECONNECT_DELAY_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatWatchdogTimer: ReturnType<typeof setInterval> | null = null
  let lastPingAt = Date.now()

  function clearTimers() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatWatchdogTimer !== null) {
      clearInterval(heartbeatWatchdogTimer)
      heartbeatWatchdogTimer = null
    }
  }

  function scheduleReconnect() {
    if (manualDisconnect || authFailed || reconnectTimer !== null) return
    status.value = 'reconnecting'
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (robotId && robotAccessToken) connect(robotId, robotAccessToken)
    }, reconnectDelayMs)
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS)
  }

  function startHeartbeatWatchdog() {
    lastPingAt = Date.now()
    heartbeatWatchdogTimer = setInterval(() => {
      if (Date.now() - lastPingAt > HEARTBEAT_TIMEOUT_MS) {
        ws?.close()
      }
    }, HEARTBEAT_WATCHDOG_INTERVAL_MS)
  }

  function connect(_robotId: string, _robotAccessToken: string) {
    manualDisconnect = false
    authFailed = false
    robotId = _robotId
    robotAccessToken = _robotAccessToken
    status.value = 'connecting'
    error.value = null

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}${WS_BASE}/user/robot/send_command`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      status.value = 'authenticating'
      ws!.send(JSON.stringify({ token: robotAccessToken, robot_id: robotId }))
    }

    ws.onmessage = async (event: MessageEvent) => {
      const data = JSON.parse(
        event.data instanceof Blob
        ? await event.data.text()
        : event.data
      )

      if (data && data.type === 'ping') {
        lastPingAt = Date.now()
        ws?.send(JSON.stringify({ type: 'pong' }))
        return
      }

      if (status.value === 'authenticating') {
        if (data.message === 'success auth') {
          status.value = 'connected'
          robotStatus.value = 'robot_disponible'
          reconnectDelayMs = MIN_RECONNECT_DELAY_MS
          startHeartbeatWatchdog()
        } else {
          status.value = 'error'
          error.value = data.message || 'Error de autenticación'
          authFailed = true
        }
        return
      }

      if (data && typeof data.status === 'string' && data.status in ROBOT_STATUS_MAP) {
        robotStatus.value = ROBOT_STATUS_MAP[data.status]
        return
      }

      if (messages.value.length > 5) {
        messages.value.shift()
      }

      messages.value.push(data)

      if (isJSONRPC(data) && data.method === "status.update") {
        robotState.value = data.params as RobotState
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      error.value = 'Error de conexión WebSocket'
    }

    ws.onclose = () => {
      clearTimers()
      if (manualDisconnect) {
        status.value = 'disconnected'
        return
      }
      if (authFailed) {
        status.value = 'error'
        return
      }
      scheduleReconnect()
    }
  }

  function sendCommand(method: string) {
    if (!ws || status.value !== 'connected') return

    ws.send(JSON.stringify({
      method,
      access_token: robotAccessToken,
      robot_id: robotId,
    }))
  }

  function disconnect() {
    manualDisconnect = true
    clearTimers()
    if (ws) {
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
  }

  function clearMessagesHistory() {
    messages.value = []
  }

  return {
    status: readonly(status),
    robotStatus: readonly(robotStatus),
    messages: readonly(messages),
    robotState: readonly(robotState),
    error,
    connect,
    sendCommand,
    disconnect,
    clearMessagesHistory
  }
}
```

- [ ] **Step 2: Verificar el type-check**

Run: `cd services/WebClient && npm run build`
Expected: build exitoso (incluye `vue-tsc -b`), sin errores de tipo nuevos

- [ ] **Step 3: Verificación manual en el navegador**

1. `cd services/WebClient && npm run dev`, con Api y Pi (mock) corriendo.
2. Loguearse, entrar a `RobotControlPage` de un robot conectado, confirmar que el estado pasa a `Conectado`.
3. Matar el proceso de la Api (Ctrl+C en su terminal). En la consola del navegador (DevTools) verificar que, sin recargar la página, el estado eventualmente pasa a "Reconectando..." (por `onclose`/`onerror` casi inmediato, ya que el SO cierra el socket al morir el proceso).
4. Reiniciar la Api. Verificar que el WebClient reconecta solo (sin recargar la página) y vuelve a `Conectado`.
5. (Opcional, si se cuenta con herramientas de red) Bloquear el tráfico hacia la Api sin matar el proceso (ej. firewall local) para verificar que el watchdog de heartbeat (25s) también dispara la reconexión.

- [ ] **Step 4: Commit**

```bash
git add services/WebClient/src/composables/useRobotSocket.ts
git commit -m "feat(webclient): reconexion automatica con backoff y heartbeat watchdog"
```

---

### Task 10: WebClient — mostrar el estado del robot en `RobotControlPage`

**Files:**
- Modify: `services/WebClient/src/pages/RobotControlPage.vue`

**Interfaces:**
- Consumes: `robotStatus` de `useRobotSocket()` (Task 9), `status === 'reconnecting'`.

- [ ] **Step 1: Modificar `RobotControlPage.vue`**

Reemplazar el contenido completo de `services/WebClient/src/pages/RobotControlPage.vue`:

```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useRobotSocket } from '../composables/useRobotSocket'
import RobotCommandPanel from '../components/RobotCommandPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { status, robotStatus, messages, error, connect, sendCommand, disconnect, clearMessagesHistory, robotState } = useRobotSocket()

const robotId = route.params.id as string
const robotAccessToken = history.state.robotAccessToken as string | undefined
const robotName = history.state.robotName as string | undefined

onMounted(() => {
  if (!robotAccessToken || !auth.token) {
    router.push('/dashboard')
    return
  }
  connect(robotId, robotAccessToken)
})

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <hgroup>
    <h2>{{ robotName || robotId }}</h2>
    <p>
      Estado:
      <span v-if="status === 'connected'">Conectado</span>
      <span v-else-if="status === 'connecting'" aria-busy="true">Conectando...</span>
      <span v-else-if="status === 'authenticating'" aria-busy="true">Autenticando...</span>
      <span v-else-if="status === 'reconnecting'" aria-busy="true">Reconectando...</span>
      <span v-else-if="status === 'error'">Error: {{ error }}</span>
      <span v-else>Desconectado</span>
    </p>
    <p v-if="status === 'connected' && robotStatus !== 'robot_disponible'">
      <span v-if="robotStatus === 'robot_desconectado_reconectando'" aria-busy="true">
        El robot se desconectó, reconectando...
      </span>
      <span v-else-if="robotStatus === 'robot_no_disponible'">
        El robot no está disponible.
      </span>
    </p>
  </hgroup>

  <RobotCommandPanel
    :status="status"
    :messages="messages"
    :robotState="robotState"
    @send="sendCommand"
    @clear="clearMessagesHistory"
  />
</template>
```

- [ ] **Step 2: Verificar el type-check**

Run: `cd services/WebClient && npm run build`
Expected: build exitoso

- [ ] **Step 3: Verificación manual en el navegador**

1. Con Api + Pi (mock) corriendo, conectarse a un robot desde `RobotControlPage`.
2. Matar el proceso de la Pi (Ctrl+C). Verificar en la UI el mensaje "El robot se desconectó, reconectando...".
3. Reiniciar la Pi dentro de los 120s. Verificar que el mensaje desaparece (vuelve a `robot_disponible`) sin recargar la página ni reconectar el WebClient.
4. Repetir el punto 2 y dejar pasar más de 120s sin reiniciar la Pi: verificar que aparece "El robot no está disponible." y luego el estado general pasa a "Reconectando..." (porque la Api cierra el WS del usuario al agotarse el timeout).

- [ ] **Step 4: Commit**

```bash
git add services/WebClient/src/pages/RobotControlPage.vue
git commit -m "feat(webclient): mostrar estado de reconexion del robot en RobotControlPage"
```

---

### Task 11: Verificación end-to-end del flujo completo

**Files:** ninguno (solo verificación manual, no hay cambios de código en esta tarea)

- [ ] **Step 1: Levantar el sistema completo en modo demo**

```bash
docker network create ciie-test  # si no existe ya
cd services/Db && make up_db.dev.detached && make migrate_db && make seed_apply
cd ../Api && make up_dev &
cd ../RaspberryPi && MOCK_ROBOT=1 CREATE_DEFAULT_METADATA=1 uv run python -m controller &
cd ../WebClient && npm run dev &
```

- [ ] **Step 2: Escenario 1 — la Pi se cae y no vuelve (cierre limpio)**

1. Aprobar el robot (admin) y conectar un usuario desde el WebClient.
2. Matar el proceso `controller` (Ctrl+C) — esto cierra el WS limpiamente.
3. Verificar: la Api limpia el registro de inmediato (log `Conexión del robot ... cerrada limpiamente`), y el usuario ve que su sesión termina (mensaje de error / desconexión), consistente con "cierre limpio = irrecuperable".

- [ ] **Step 3: Escenario 2 — la Pi se cae por corte de red (timeout de heartbeat) y reconecta a tiempo**

1. Conectar un usuario al robot.
2. Cortar la conexión sin que la Pi cierre prolijo. Si no se cuenta con herramientas de red para simular esto, alternativa: agregar temporalmente un `await asyncio.sleep(3600)` al inicio de `WsStrategy.receive()` en una copia de prueba para simular un proceso colgado que no responde heartbeat (revertir después de probar) — o directamente confiar en los tests automatizados de Task 6/7/8, que ya cubren esta lógica en aislamiento, y limitarse a verificar el escenario 1 y 3 manualmente (más fáciles de reproducir sin herramientas de red).
3. Verificar: el usuario ve "robot desconectado, reconectando..." y no pierde su sesión.
4. Reiniciar el proceso de la Pi dentro de los 120s. Verificar: el usuario ve "robot reconectado" y puede seguir enviando comandos sin haber tocado su propia conexión.

- [ ] **Step 4: Escenario 3 — la Api se cae y el WebClient reconecta solo**

1. Con un usuario conectado, matar el proceso de la Api.
2. Verificar en el navegador (sin recargar la página) que el estado pasa a "Reconectando...".
3. Reiniciar la Api. Verificar que el WebClient reconecta solo y vuelve a "Conectado" con el mismo robot.

- [ ] **Step 5: Correr toda la suite automatizada una vez más, de punta a punta**

```bash
cd services/Api && uv run pytest -v
cd ../RaspberryPi && uv run pytest -v
cd ../WebClient && npm run build
```

Expected: todo PASS/build exitoso.
