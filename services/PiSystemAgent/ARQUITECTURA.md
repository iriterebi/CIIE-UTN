# Arquitectura

```
------------------------------------------------------------------------
|                                                                      |
| [micro core] ──strategy── [ROS 2 / mock]                             |
|     │            (local)                                             |
|     ├────────strategy── [WS / mqtt / http pull-push loop]  ──────────|───→ API
|     │            (remoto)                                            |
|     └──────── [Unix Socket] ◄────────────────────────────────────────|───→ [cli]
|                                                                      |
------------------------------------------------------------------------
```

- **micro core** (asyncio, main thread): enrutador puro — mueve mensajes en formato interno entre adapters, no transforma datos. Cada adapter traduce entre su protocolo externo y el formato interno. Conecta dos strategies y el socket de gestión
- **strategy local**: módulo de conexión con el robot. Intercambiable. Hoy hay dos implementaciones en `strategy/local/` (el serial directo al Arduino se eliminó: el Arduino lo maneja el agente ROS de PiRobotDriver):
  - `MockStrategy` — sin hardware (modo demo).
  - `Ros2Strategy` — IPC ROS 2 sobre DDS: daemon thread con `rclpy.spin()`, publica comandos en `inorbit/custom_command` y suscribe telemetría `Key=Value` en `inorbit/custom_data` (`rclpy` con import diferido). El agente ROS contraparte es fire-and-forget (no responde comandos).
- **strategy remoto** (WS por defecto): módulo de conexión con la API. Corre en asyncio del core. Intercambiable (alternativa futura: MQTT)
- **Unix Socket**: interfaz de gestión (start/stop/status). Solo gestión, no datos
- **cli**: proceso separado, se conecta al core a través del socket. Habilita que el core corra como daemon (systemd, etc.)

---

## Flujo de comandos: despacho y respuestas

Cada strategy local (`MockStrategy`, `Ros2Strategy`) extiende
`OutboxLocalStrategy` (`controller/strategy/base.py`). Ahí vive, una sola vez, el modelo
de correlación entre comandos y respuestas: una cola `asyncio.Queue[RobotResponse]` por
strategy, alimentada por tres productores y drenada por un único consumidor.

**Productores:**
- `send()` — despacha el comando vía `json_rpc.dispatch()` y encola el resultado del
  despacho (con el `id` que traía el comando).
- `_response_loop` — drena de forma continua el output espontáneo del robot
  (`robot.read_response()`, corrido en un hilo del executor), haya o no un usuario
  conectado.
- `_telemetry_loop` — cada `STATUS_INTERVAL_SEC` (5s) encola un snapshot de
  `robot.get_status()`.

**Consumidor:** `receive()` es el único punto donde un `RobotResponse` se traduce a un
sobre JSON-RPC, vía `json_rpc.to_jsonrpc()`.

### "Despacho" no es "ejecución"

Despachar un comando significa que se validó contra los descriptores que el robot
publicó y que se escribió/publicó. **No** afirma que el robot lo haya ejecutado: ni el
Arduino ni el agente ROS 2 confirman ejecución de vuelta. La salida real del robot llega
por un camino separado — `_response_loop` — como notification sin `id`.

### Regla de correlación

El TIPO concreto de `RobotResponse` decide el sobre JSON-RPC; `request_id` sólo rellena
el campo `id`, nunca decide el sobre. `DispatchOkRobotResponse`/`DispatchErrorRobotResponse`
(lo que produce `send()`) se traducen siempre a `JsonRpcResponse`, con cualquier id que
haya traído el comando — incluido `null`. Todo lo demás que el robot emite
espontáneamente (output crudo, descriptores de comandos, telemetría) se traduce a
`JsonRpcNotification`. Discriminar por tipo y no por valor es deliberado: el WebClient
no manda `id` en sus comandos, así que una regla basada en "¿tiene `request_id`?"
degradaría todo resultado de despacho a notification.

### Contrato del controlador

`RobotMockController` y `Ros2Controller` comparten la misma
firma:

- `send_command(command: str) -> None` — valida y despacha; levanta
  `InvalidCommandError` / `ConnectionError` / `OSError`; nunca acumula una respuesta.
- `read_response() -> RobotResponse | None` — bloquea hasta tener output; `None` es la
  señal de parada.
- `stop_reading() -> None` — desbloquea un `read_response()` pendiente; idempotente.
- `execute_sequence(commands) -> None` — sólo envía, nunca lee.
- más `connect()`, `disconnect()`, `get_status()`.

El contrato es uniforme en firma, no en validación: sólo `RobotMockController` (con un
`RobotCommandRecord` seedeado a mano) y `Ros2Controller` (poblado por lo que publica el
agente ROS real) tienen descriptores contra los cuales validar.

### Orden de apagado

`OutboxLocalStrategy.stop()` fija un orden que costó una investigación empírica para
probar correcto: `robot.stop_reading()` → `await _stop_loops()` → `await
_disconnect_robot()`. La razón: `_response_loop` bloquea un hilo del executor en
`asyncio.to_thread(robot.read_response)`, y un hilo bloqueado ahí no se puede cancelar
— `task.cancel()` no lo interrumpe, sólo el sentinel (`None`) lo libera. Invertir el
orden deja hilos del executor vivos tras `stop()`. `connect()` en los tres controladores
resetea su estado de lectura, para que un ciclo `stop()`/`start()` disparado desde el
CLI funcione sobre la misma instancia.

---

# Plan de Refactor

este es un plan general para el refactor del subporyecto, para movernos a la nueva arquitectura. Lo haremos en 2 grandes bloques

## 1. Estructura

Cambiaremos al estructura del código a la nueva arquitectura, procurando mantener la funcionalidad actual. Para ello replantearmoes lo que tenemos:

- Strategy Interno: @controller/robot/ tiene la implementación de la comunicación interna, tanto ROS 2 como mock.
- Strategy Externo: la conexión remota vive en @controller/strategy/remote/ — actualmente WS directo a la API (`ws_strategy.py`).

Como no tenemos "micro core", esto será lo nuevo, para esta etapa conectará los strategies y escuchará el Unix Socket (y nada más)


## 2. Cli v1.1

Crearemos un Cli muy simple que hable con el sistema, este solo pedirá estatus del sistema y el "micro core" debe responderle. Esta etapa está para plantear el cli

## 3. Cli v1.2

Agregaremos un comando switch: el "strategy interno" mock tiene un loop que envía telemetría mock, este switch permitirá habilitar/deshabilitar ese loop.
Esta etapa es para plantear el funcionamiento de control del cli y el micro core

## 4. Strategy Selection

Acá agregaremos la posibilidad de seleccionar los strategies, por ahora solo tenemos uno remoto y dos locales, pero es suficiente para plantear el mecanismo de selección.

### 4.1

Agregaremos nueva información de status que será mostrada por el cli cuando se pida:

```
Estado de conexión
- strategy remoto: [CONECTADO/DESCONECTADO] [<strategy seleccionado>|<NONE>]
- strategy local: [CONECTADO/DESCONECTADO] [<strategy seleccionado>|<NONE>]
```

### 4.2.1 boot: selección de los strategies al inicio
se selecciona según config (.env)


## 5. WS

Crearemos el strategy remoto para el WS

NOTA: Cada strategy debe pedir sus propias credenciales, ya que las credenciales provistas por la API son diferentes según el mecanismo de comunicación.

## 6. Select + hot-swap

Selección de strategies en vuelo desde el CLI. Se agregan subcomandos para cambiar el strategy remoto y el local. El cambio implica "apagar" el strategy (deben tener una subrutinna start, stop, y pause), desconectar el enrutado (romper el pipe), Conectar el nuevo strategy y start.

El cli tendrá el formato:
```bash
# para conección remota
cli.py coneccion remota [...]

# para conección local
cli.py coneccion local [...]

# el lenguaje es el siguiente
cli.py coneccion [remota|local] [status|start|stop|pause]
cli.py coneccion [remota|local] [select] [list|<strategy_name>] [[<argumentos del strategy>...]]
```

esto agrega varios conceptos:
- un strategy puede ser pausado (no se desconecta pero se interrumpe el envío y recerpción de mensajes (se encolan))
- select list: lista los strategies disponibles, esto involucra un registro de strategies disponibles en lugar de simples if/else
- los strategies pueden recibir argumentos propios para su start
- un strategy no puede ser cambiado si está running o pausado (el cambio debe lanzar error)
- el registro de argumentos ahora introduce el concepto de subargumentos (o scoped args)

