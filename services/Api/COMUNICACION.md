# Arquitectura de Comunicación Usuario ↔ Robot

## Motivación

El robot se conecta directamente a la API por WebSocket (`/m2m/robot/connect`) — no hay intermediarios. El diseño abstrae la capa de transporte detrás de adapters (`StreamSource`) y conexiones (`StreamConnection`) para que la lógica del pipe usuario↔robot no dependa del protocolo concreto. Migrar a otro transporte en el futuro (ej. MQTT, otro mecanismo de IPC) implica agregar un nuevo adapter, no reescribir el pipe.

## Flujo de datos

### Robot → Usuario

```
robot ws >- [controller] -> ProxyStreamSource >- RobotConnection --[pipe]--> UserConnection -> UserStreamSource -> user ws
```

### Usuario → Robot

```
user ws >--[UserStreamSource]-- UserConnection --[pipe]--> RobotConnection --[ProxyStreamSource]--> robot ws
```

### Notación

- `>-` — pull (el componente a la izquierda tira datos del anterior)
- `->` — push directo
- `--[X]-->` y `>--[X]--` — X actúa como intermediario transparente que estabiliza la conexión (el primero es push, el segundo el pull)

## Componentes

| Componente | Responsabilidad |
|---|---|
| **Controller m2m** (`routes/m2m.py`) | Maneja el WS del robot: autenticación JWT, loop de mensajes, alimenta `ProxyStreamSource` via `enqueue_data()` |
| **ProxyStreamSource** (`adapters/proxy_stream_source.py`) | Adapter callback-based que desacopla el WS del robot del pipe. El controller es productor, el pipe es consumidor |
| **RobotConnection** (`repositories/stream_entities.py`) | Conexión del lado robot. Persiste entre pipes. Trackea estado idle. Solo corre `connect()` dentro del contexto de un pipe |
| **Pipe** (`UsersXRobotMapType` en `repositories/stream_entities.py`) | Conecta `UserConnection` ↔ `RobotConnection`. Corre ambos `connect()` en un `TaskGroup`. Intermediario transparente |
| **UserConnection** (`repositories/stream_entities.py`) | Conexión del lado usuario. Se crea y destruye con cada sesión WS |
| **UserStreamSource** (`adapters/user_stream_source.py`) | Adapter del WS del usuario. Valida payload (Pydantic) per-mensaje. Errores no matan la conexión |
| **Orquestador** (`services/ipc_user_robot_comunication.py`) | `UserToRobotComunication` — autentica al usuario, obtiene/crea conexiones del repository, arma el pipe |
| **RobotConnectionRepository** (`repositories/robot_connection.py`) | Fuente de verdad de conexiones activas. Garantiza consistencia (no duplicados, limpieza) |

## Ciclo de vida

1. **Robot se conecta** — `WS /m2m/robot/connect` → controller autentica con JWT, crea `ProxyStreamSource`, registra `RobotConnection` en el repository. El controller queda en loop leyendo el WS y alimentando la queue
2. **Usuario se conecta** — `WS /user/robot/send_command` → orquestador autentica, crea `UserConnection`, busca `RobotConnection` existente en el repository, crea el pipe (`addUserXRobotConnection`), ejecuta `bidirectionalPipe.connect()`
3. **Pipe activo** — `RobotConnection.connect()` tira de la queue del `ProxyStreamSource`. `UserConnection.connect()` tira del WS del usuario. Ambos corren concurrentes en un `TaskGroup`
4. **Usuario se desconecta** — `UserConnection._on_disconnect()` cierra el WS. `RobotConnection._on_disconnect()` marca como idle, notifica `on_idle_changed(True)` al stream source (descarta queue). La `RobotConnection` persiste en el repository
5. **Nuevo usuario se conecta al mismo robot** — el orquestador encuentra la `RobotConnection` existente, crea nuevo pipe. `on_idle_changed(False)` reactiva el stream source

## Adapters disponibles

| Adapter | Uso | Estado |
|---|---|---|
| `UserStreamSource` | WS del usuario → `StreamSource` | Estable |
| `ProxyStreamSource` | Callback-based, alimentado por el controller del WS del robot | En uso |

## Estructura de archivos

| Archivo | Contenido | Por qué existe |
|---|---|---|
| `adapters/user_stream_source.py` | `UserStreamSource` | Adapta WS del usuario a `StreamSource`, valida payload per-mensaje sin matar la conexión |
| `adapters/proxy_stream_source.py` | `ProxyStreamSource` | Adapter callback-based que invierte el control: el controller m2m maneja el WS y alimenta la queue. Desacopla el ciclo de vida del WS del robot del pipe |
| `repositories/stream_entities.py` | `StreamSource`, `StreamConnection`, `RobotConnection`, `UserConnection`, `UsersXRobotMapType` | Entidades extraídas del repository. `StreamConnection` es abstracta con template method `_on_disconnect` para cleanup asimétrico (usuario cierra, robot persiste) |
| `repositories/robot_connection.py` | `RobotConnectionRepository`, `RobotInUseError` | Fuente de verdad de conexiones activas. Garantiza consistencia (no duplicados, limpieza). Las conexiones del robot persisten entre pipes |
| `services/ipc_user_robot_comunication.py` | `UserToRobotComunication` | Orquestador del lado usuario: autentica, obtiene/crea conexiones, arma el pipe |
| `routes/m2m.py` | Controller `/connect` | Endpoint WS del robot (prototipo). Autentica con JWT, registra `RobotConnection` en el repository, loop manual de mensajes |

## Deuda técnica pendiente

- Validación profunda del payload (más allá de `RRobotCommand`)
- Verificación del `access_token` per-sesión
- Replanteo de `UserRobotAccessSession`
- Implementar backpressure real con `on_idle_changed`
- Limpiar prototipo del controller m2m (nombres placeholder `idk`/`idk2`)
