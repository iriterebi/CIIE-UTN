# Diseño: desacople de despacho y respuestas en el agente de la Pi

- **Fecha**: 2026-10-05
- **Servicios**: `services/PiSystemAgent/`
- **Estado**: aprobado, pendiente de plan de implementación

## Problema

La implementación previa al soporte de autodescubrimiento de comandos asumía un flujo
request→response implícito: *un comando produce exactamente una respuesta, y esa respuesta es
la del comando*. `handle_json_rpc` lo codificaba literalmente:

```python
await loop.run_in_executor(None, robot.send_command, raw_command)
response = await loop.run_in_executor(None, robot.read_response)
for resp in response.each():
    ...
```

El autodescubrimiento rompió esa suposición. El robot ahora emite mensajes por su cuenta
(los descriptores `commands=` que llegan por telemetría DDS) que no corresponden a ningún
comando del usuario. `read_response()` pasó a drenar una lista acumulada, y la relación
implícita se perdió sin nada que la reemplace. De ahí salen tres defectos confirmados:

- **#3 — el `id` de JSON-RPC se descarta** (`json_rpc.py:132`): `yield JsonRpcResponse(result=result,
  id=None)`. Con dos requests en vuelo el cliente no puede emparejar respuestas.
- **#4 — centinela `""` en la ruta serial** (`robot_controller.py:61`): `StrRobotResponse("",
  response)`. El string vacío no es `None`, así que el handler toma la rama equivocada y reporta
  `method: ""` (pierde el nombre real) con `id: None` en cada respuesta del Arduino.
- **#7 — la lista de respuestas crece sin tope** (`ros2_controller.py:353`): `_handle_data`
  acumula un `CommandsDescriptionRobotResponse` por cada mensaje `commands=`, pero sólo se drena
  en `read_response()`, que únicamente se llama cuando un usuario manda un comando. Sin nadie
  conectado crece sin límite, y el siguiente comando descarga todo el backlog de golpe.
  `execute_sequence` nunca drena, así que sus acks se filtran en la respuesta de un comando
  posterior no relacionado.

Los tres son el mismo problema de fondo: no hay un modelo explícito de qué está correlacionado
con qué.

## Objetivo

Reemplazar la correlación implícita por una regla explícita, desacoplando el envío del comando
del envío de las respuestas, de modo que los tres defectos dejen de ser posibles por
construcción y no por disciplina del llamador.

## Fuera de alcance

- **Cambios en el WebClient.** Validado: la SPA no parsea respuestas. El panel "Respuestas"
  (`RobotCommandPanel.vue:52`) es un `JSON.stringify` crudo de los últimos 5 mensajes, y el único
  parse estructurado es `data.method === "status.update"` (`useRobotSocket.ts:136`), cuya forma no
  cambia. Las notifications nuevas caen en el mismo dump donde ya caen hoy.
- **Render de controles dinámicos a partir de `command.update`.** `RobotCommandPanel` tiene
  `start`/`stop`/`restart` hardcodeados mientras los descriptores ya llegan por el socket. Es la
  próxima feature (el placeholder `useRobotControls.ts`, hoy vacío), no este refactor.
- **Que el cliente mande un `id` JSON-RPC.** Hoy `sendCommand` envía `{method, access_token,
  robot_id}` sin campo `id`. Arreglar el #3 es correcto a nivel protocolo, pero no será observable
  end-to-end hasta que el cliente mande ids: **la verificación del #3 es por test unitario, no por
  inspección de la UI.**
- **Desambiguar comandos tipados.** `TypedRobotCommand` ignora `command_name` por diseño (igual
  que `ToggleRobotCommand`): `command_name` es metadata para la UI, no parte del wire. Con dos
  comandos `uint` mandar `"50"` matchea ambos. Es una limitación aceptada del controlador
  low-level, no un bug de esta capa.
- **Hallazgos #9 y #10** (falta `__init__.py` en `controller/tests/`, `cli_parse_args=True` a nivel
  de módulo). Pendientes aparte. Nota: **#9 y #10 mantienen CI rojo**
  — `pytest` aborta en colección y muere con `SystemExit: 2` ante cualquier flag. Mientras sigan
  abiertos, los tests de este trabajo se corren invocando pytest con `sys.argv` limpio.

## Decisiones tomadas

### 1. Lo único correlacionado con el `id` es el despacho

Ni el Arduino ni el agente ROS 2 pueden correlacionar: el primero devuelve texto plano sin eco
del id, el segundo es fire-and-forget y no responde comandos. No hay manera realista de asociar
la salida real del robot al comando que la originó, así que el diseño deja de fingir que la hay.

> **El tipo del `RobotResponse` decide el sobre; `request_id` sólo rellena el campo `id`.**
> `DispatchOkRobotResponse` / `DispatchErrorRobotResponse` → `JsonRpcResponse` (con el id que
> traigan, aunque sea `null`). Cualquier otro → `JsonRpcNotification`.

La regla discrimina por **tipo**, no por valor de `request_id`. Hacerlo por
`request_id is not None` sería incorrecto: el WebClient hoy no manda `id`, así que `command.id`
llega `None` y todo resultado de despacho degradaría a notification. El `request_id` es el valor
que se copia al sobre, no el criterio para elegirlo.

Esa regla reemplaza la heurística `resp.command is not None` de hoy, que es exactamente la causa
del #4.

"Despacho" significa: el comando se validó contra el descriptor y se escribió/publicó sin error.
No significa que el robot lo haya ejecutado. La salida real del robot llega después, como
notification sin id.

**Consecuencia: el `id` nunca baja al controlador.** `send_command` es síncrono (`ser.write` /
`publisher.publish`), así que su éxito o fallo se conoce en el mismo `await`, y la strategy —que
ya tiene el id en la mano— construye ahí mismo la respuesta correlacionada. El controlador queda
id-agnóstico. Esto descarta el plan original de propagar el id hacia abajo: resultó innecesario.

### 2. Una sola cola, objetos de dominio polimórficos

Hoy el `_outbox` ya es una sola cola, pero lo que entra son `dict` ya serializados
(`model_dump(mode="json")` repetido en cuatro sitios), lo que impide tratarlos polimórficamente.

La cola pasa a llevar `RobotResponse`. La telemetría se suma al mismo árbol de tipos como
`StatusRobotResponse`. La traducción a JSON-RPC ocurre en **un solo lugar**, `receive()`.

Tres productores, una cola, un consumidor:

```
                      ┌─────────────────────────────────────┐
 core.send(msg) ──────│ send()                              │
                      │   dispatch(cmd, robot) ──┐          │
                      └──────────────────────────│──────────┘
                                                 │ DispatchOk/Error (request_id=N)
                                                 ▼
 robot (spin thread / readline) ──► _response_loop ──►  _outbox        ──► receive()
                                      StrRobotResponse       Queue          to_jsonrpc()
                                      CommandsDescription…   [RobotResponse] .model_dump()
 timer 5s ────────────────────────► _telemetry_loop ──►                        │
                                      StatusRobotResponse                      ▼
                                                                        core.receive()
```

**No se garantiza orden entre el ack de despacho y el output real** — son productores distintos
sobre la misma cola. Decisión explícita: no importa para este sistema.

### 3. Nuevo contrato del controlador

Igual para los tres (`Ros2Controller`, `RobotController`, `RobotMockController`):

```python
send_command(command: str) -> None
    # valida contra el descriptor y despacha.
    # raises InvalidCommandError | ConnectionError | OSError
    # YA NO empuja nada a la lista de respuestas

read_response() -> RobotResponse
    # BLOQUEA hasta que haya output. Devuelve UNO, nunca un Composed.
```

Dos cambios de fondo:

- **`send_command` levanta en vez de acumular.** Hoy `Ros2Controller.send_command` empuja un
  `CommandErrorRobotResponse` a la lista ante un comando inválido — por eso el error salía sin id.
  Levantando, la strategy puede responder con id.
- **`read_response` bloquea en vez de drenar.** Pasa de "devolvé lo que haya ahora" a "esperá a que
  haya algo". Eso convierte `list + Lock` en `queue.Queue` (thread-safe, `get()` bloqueante) para
  ROS 2 y mock. El serial no necesita cola: su `ser.readline()` ya *es* el bloqueo.

**`ComposedRobotResponse` y `each()` desaparecen.** Existían sólo para empaquetar la ráfaga que el
drenaje producía; sin ráfagas, sobran.

### 4. Árbol de tipos movido a `controller/robot/responses.py`

Hoy `robot_mock_controller.py` y `json_rpc.py` importan sus tipos base desde `ros2_controller.py`,
un acoplamiento accidental que empeora con este cambio.

```
RobotResponse(request_id: str | int | None = None)
├─ StrRobotResponse(text)                     output crudo  → notification "robot.output"
├─ CommandsDescriptionRobotResponse(record)   descriptores  → notification "command.update"
├─ StatusRobotResponse(dict)          [nuevo] telemetría    → notification "status.update"
├─ DispatchOkRobotResponse(method)    [nuevo] despacho ok   → response(id)
└─ DispatchErrorRobotResponse(m, err) [nuevo] despacho falló→ response(id, error)
```

**El campo `command` desaparece de la clase base.** Hoy es `command: Final[str | None]` y sirve de
doble propósito: marcar correlación (la heurística rota del #4) y llevar el nombre del método para
`JsonRpcResult.method`. El primer propósito lo toma `request_id`; el segundo sólo lo necesitan los
dos tipos de despacho, que lo llevan como campo propio (`method`). Las notifications no lo usan.

`InvalidCommandError` vive también en `controller/robot/responses.py`, junto al árbol de tipos que
la produce.

La clase base pierde el `__str__` abstracto roto (`def __str__(self) -> str: ...` devuelve `None`
→ `TypeError` para cualquier subclase que no lo sobreescriba). Eso cierra el **#11** de paso.

El árbol `RobotCommand` (`LiteralRobotCommand`, `ToggleRobotCommand`, `TypedRobotCommand`,
`RobotCommandRecord`, `parse_commands`) se mueve junto con él.

### 5. `handle_json_rpc` partido en dos

```python
async def dispatch(command: JsonRpcCommand, robot) -> RobotResponse
    # valida params (incluido execute_sequence), despacha en executor,
    # devuelve DispatchOk/DispatchError con request_id=command.id
    # NO es generador: una entrada → una salida

def to_jsonrpc(resp: RobotResponse) -> JsonRpcResponse | JsonRpcNotification
    # la regla de la Decisión 1
```

El async generator `handle_json_rpc` desaparece.

Esto unifica además la forma de los errores: hoy un `CommandErrorRobotResponse` *con* comando sale
como `result.status == "error"` (respuesta con forma de éxito) y uno *sin* comando sale como
`error` con `code: 1`, que no es un código JSON-RPC definido. Con el rediseño hay una sola forma:
`DispatchError` → `JsonRpcResponse(error=…, id=…)`, nunca un `result` con `status="error"`.

Códigos, fijados explícitamente:

| Causa | Código |
|---|---|
| `params` mal formados (ej. `commands` no es lista) | `-32602` (Invalid params) |
| `InvalidCommandError` — no matchea el descriptor | `-32602` (Invalid params) |
| `ConnectionError` / `OSError` — falla de transporte | `-32603` (Internal error) |

Eso cierra el **#12**.

### 6. Base compartida, sólo para la cola

`OutboxLocalStrategy(LocalStrategy)` en `strategy/base.py` aporta **la cola y lo que la toca**:
`_outbox`, `receive()`, `send()`, `_response_loop`, `_telemetry_loop`, `_start_loops()`,
`_stop_loops()`.

Cada strategy conserva su `__init__`, `start` y `stop`, que es donde genuinamente difieren (mock
conecta sync; serial y ROS 2 van a executor). La base declara `_robot` como atributo que la
subclase setea.

No se deduplica el resto de la triplicación existente entre las tres strategies: queda fuera del
alcance de este trabajo.

### 7. Manejo de threads y parada limpia

El `_response_loop` deja un hilo bloqueado permanentemente en `read_response()`. Con el
`ThreadPoolExecutor` por defecto eso ocuparía un worker fijo, así que usa `asyncio.to_thread`.

Para poder parar el loop:

- **Serial**: `timeout` en el puerto. `readline()` devuelve `""` al vencer; el loop descarta el
  vacío y reintenta, lo que le da un punto de cancelación periódico.
- **ROS 2 y mock**: sentinel en la cola al hacer `stop()`, para desbloquear el `get()`.

## Qué cierra

| Hallazgo | Cómo |
|---|---|
| **#3** id perdido | El id vive en `DispatchOk/Error.request_id`; `to_jsonrpc` lo propaga. Una respuesta con id por comando, siempre |
| **#4** centinela `""` | El output del serial sale como `StrRobotResponse(request_id=None)` → notification. El centinela desaparece |
| **#7** lista sin tope | El `_response_loop` drena continuamente, haya usuario o no. Sin crecimiento ni ráfagas. `execute_sequence` deja de filtrar acks |
| **#11** `__str__` roto | Desaparece con el rediseño de la clase base |
| **#12** error inconsistente | Una sola forma de error, con código JSON-RPC real |

## Testing

`controller/tests/test_ros2.py` ya cubre el autodescubrimiento (parsing de descriptores,
serialización de `toDict`, validación `uint`, rechazo de comandos desconocidos, contención de
excepciones en el callback de spin). Esos tests se conservan.

Cambios y agregados necesarios:

- **`test_send_command_rejects_unknown_command` se reescribe**: hoy asume que `send_command`
  acumula un error en la lista; con el nuevo contrato debe esperar que levante.
- **`test_read_response_returns_synthetic_ack` se reescribe** (hallazgo #8): `_SENT_ACK` deja de ser
  output falso del robot y pasa a ser el payload del dispatch-ok.
- **Correlación del id**: `dispatch()` devuelve `request_id == command.id`; `to_jsonrpc` lo emite en
  la respuesta. Un test por rama (ok y error). Es la única verificación posible del #3 — ver
  "Fuera de alcance".
- **Regla de enrutado de `to_jsonrpc`**: tabla de `RobotResponse` → `JsonRpcResponse` vs
  `JsonRpcNotification`, cubriendo las cinco subclases.
- **Drenaje continuo (#7)**: empujar N mensajes `commands=` sin mandar ningún comando y verificar
  que la cola del controlador no crece y que salen N notifications.
- **Ruta serial (#4)**: el output del Arduino sale como notification sin id y sin `method: ""`.
- **Parada limpia**: `stop()` termina el `_response_loop` sin dejar el hilo colgado, en los tres
  controladores.

El modo demo (`MOCK_ROBOT=1`) debe seguir funcionando end-to-end sin hardware: es el criterio de
aceptación mínimo antes de dar el trabajo por terminado.

## Riesgos

1. **El cambio de contrato de `send_command` (levanta en vez de acumular) toca los tres
   controladores a la vez.** No hay forma de hacerlo incremental manteniendo un solo `handle_json_rpc`.
   Mitigación: los tres son chicos y `test_ros2.py` ya cubre el camino de ROS 2 y mock.

2. **El serial es el menos cubierto por tests** y es donde el `timeout` del puerto introduce
   comportamiento nuevo. No hay hardware en dev para verificarlo; se prueba con un doble de
   `serial.Serial`.

3. **Un hilo bloqueado por strategy local.** Hoy hay una sola strategy local activa, así que es un
   hilo. Si en el futuro se activan varias simultáneamente, hay que revisar.
