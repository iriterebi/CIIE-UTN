# Compendio: Análisis Arquitectural de Labs Remoto
> Historial de razonamiento y decisiones técnicas — para continuar en nueva sesión

---

## Contexto del Proyecto

**Labs Remoto** es un sistema distribuido que permite a usuarios (profesores y alumnos) controlar robots físicos de forma remota a través de una interfaz web. Es un monorepo con múltiples servicios, actualmente en etapa de prototipo/desarrollo activo.

- **Stack principal**: Python 3.13.7+ (FastAPI), Vue 3 + TypeScript, PostgreSQL 17.5, ROS 2 Humble + rosbridge
- **Deploy**: Podman Quadlets + systemd en servidor de la facultad
- **Dev**: Docker Compose

---

## Arquitectura Actual (documentada)

### Diagrama general

```
Browser (Vue 3 SPA)
    │ HTTP / WebSocket
    ▼
nginx (proxy container, :80)
    ├──► webclient (nginx, SPA estática)
    ├──► api:8000 (FastAPI)
    └──► rosbridge:9090 (solo intranet)

API (FastAPI, monolito modular)
    ├──► PostgreSQL :5432
    └──► rosbridge :9090 (WebSocket — protocolo rosbridge)

rosbridge (container en el servidor)
    ◄──► API (cliente WS)
    ◄──► RaspberryPi (cliente WS, vía red interna de la facultad)

RaspberryPi (en el robot físico)
    ├── nodos Python (lógica de control)
    └──► Arduino (serial USB) → 7 servomotores
```

### Flujo de comunicación usuario→robot

```
Usuario ──WS──► API ──publish /robot/r<b32>/command──► rosbridge ──► RaspberryPi
                 ▲                                          │
                 └──────────── asyncio.Queue ───────────────┘
                              (fan-out de respuestas)
```

### Componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| WebClient | Vue 3, Vite, PicoCSS, Pinia | SPA: auth, selección de robot, envío de comandos |
| API | FastAPI, SQLModel | Monolito modular: auth, sesiones, proxy WS usuario↔robot |
| DB | PostgreSQL 17.5 | Persistencia usuarios, robots, auditoría |
| rosbridge | rosbridge_suite ROS 2 | Puente WebSocket/JSON ↔ ROS DDS |
| RaspberryPi | Python | Controlador del robot: recibe comandos, habla con Arduino |
| Arduino | C++ | Control de 7 servomotores del brazo robótico |

### Módulos internos de la API

| Módulo | Rutas | Responsabilidad |
|---|---|---|
| `auth` | `/auth/*` | Login, signup, token de acceso a robot |
| `robot` (admin) | `/admin/robot/*` | CRUD de robots, comandos admin |
| `robot` (m2m) | `/m2m/robot/*` | Registro y handshake de robots |
| `robot` (user) | `/user/robot/*` | WebSocket para usuarios |

### Protocolos

- **HTTP/REST**: Frontend↔API (auth, CRUD), Pi↔API (registro, handshake)
- **WebSocket**: Frontend↔API (comandos realtime), API↔rosbridge, Pi↔rosbridge
- **JSON-RPC 2.0**: Protocolo de mensajes para comandos a robots (sobre WS)
- **Serial USB**: Pi↔Arduino

### Topics ROS

Los UUIDs de robots se codifican en **Crockford Base32** con prefijo `r` (ROS 2 no permite tokens que empiecen con número):

- `/robot/r<base32>/command`
- `/robot/r<base32>/response`
- `/robot/r<base32>/status`

### Autenticación

Tres tipos de JWT:

| Token | Generado en | Uso |
|---|---|---|
| Usuario | `/auth/login` | Acceso general a la API |
| Robot access | `/auth/request_robot_access` | Permiso para controlar un robot específico |
| Robot (M2M) | `/m2m/robot/handshake` | Conexión del robot al sistema |

Flujo de autorización para controlar un robot:
1. Usuario se autentica → JWT de usuario
2. Usuario solicita acceso a robot → JWT robot_access
3. Usuario conecta WS y envía token
4. Cada comando lleva `access_token` + `robot_id`, la API valida ambos

Roles: `profe` (admin, acceso `/admin/*`) y `alumno` (user, acceso `/user/*`)

### Handshake robot (self-registration)

1. Pi genera credenciales y hace `POST /m2m/register` → queda en estado `pending`
2. Pi hace polling a `POST /m2m/handshake` con backoff exponencial
3. Admin aprueba el robot (`POST /admin/robot/{id}/approve`)
4. Pi recibe JWT + topic base → se conecta a rosbridge y se suscribe a su topic de comandos

### Detalles del módulo realtime (API)

- Conexión **única ("master")** de la API a rosbridge (embudo)
- **asyncio.Queue por usuario** — el listener de rosbridge hace fan-out de respuestas
- **Suscripción lazy**: se suscribe a los topics de un robot la primera vez que un usuario envía un comando
- **Reconexión automática** con backoff exponencial si se pierde la conexión a rosbridge
- La Pi también se conecta a rosbridge como cliente WS (no habla DDS directamente)

### Deploy producción (Podman Quadlets + systemd)

5 servicios en la red `labs-remoto`:

| Servicio | Imagen | Puerto expuesto |
|---|---|---|
| proxy | nginx:alpine | `0.0.0.0:80` (entrada pública) |
| api | localhost/labs-remoto/api | — (solo via proxy) |
| webclient | localhost/labs-remoto/webclient | — (solo via proxy) |
| rosbridge | localhost/labs-remoto/rosbridge | `127.0.0.1:9090` (debug/intranet) |
| db | postgres:17.5-alpine | `127.0.0.1:5432` (migraciones) |

Cadena de dependencias: `db → api`, `rosbridge → api`, `api + webclient → proxy`

Build: se compila localmente y se transfiere por SSH (`podman save → scp → podman load`). No se compila en el servidor.

Rutas del proxy nginx:

| Path | Destino | Tipo |
|---|---|---|
| `/` | `webclient:80` | HTTP |
| `/api/*` | `api:8000` | HTTP |
| `/ws/*` | `api:8000` | WebSocket |
| `/m2m/*` | `api:8000` | HTTP (solo intranet) |
| `/rosbridge/` | `rosbridge:9090` | WebSocket (solo intranet) |

### Modo Demo

- `MOCK_ROBOT=1`: activa `RobotMockController` en la Pi, simula respuestas sin hardware
- `CREATE_DEFAULT_METADATA=1`: la Pi se auto-registra y conecta automáticamente
- DB efímera con `tmpfs` disponible para pruebas
- Toda nueva feature debe garantizar compatibilidad con modo demo

---

## Topología de Red Real

Un punto que generó confusión y fue aclarado durante el análisis:

**Lo que parecía**: rosbridge en el servidor hablando DDS con la Pi a través de la red → problema (DDS usa multicast UDP, puertos dinámicos, hostil a redes no controladas).

**Lo que realmente ocurre**: tanto la API como la Pi son **clientes WebSocket de rosbridge**. DDS queda confinado dentro del container de rosbridge en el servidor. La Pi habla el protocolo rosbridge (JSON sobre WS), no DDS directamente. Esto hace el Escenario 2 mucho más robusto de lo que parecía inicialmente.

```
[Pi] ──WS (protocolo rosbridge)──► [rosbridge container] ←──WS── [API]
                                          │
                                        [DDS interno — no cruza red]
```

La Pi se conecta al servidor a través de la **red interna de la facultad**, entrando por nginx (ruta `/rosbridge/`, solo intranet).

---

## Análisis Python vs Go para WebSockets (exploración)

Esta fue una discusión exploratoria. No hay intención de cambiar de lenguaje en el corto plazo.

### Resumen del análisis

| Aspecto | Python (FastAPI + uvicorn) | Go |
|---|---|---|
| Concurrencia | asyncio (cooperativa, GIL) | goroutines (M:N, sin GIL) |
| Latencia p99 | Buena | Superior |
| Consumo de recursos | Moderado | Muy bajo |
| Ergonomía | Alta | Media (más verbose) |
| Ecosistema ROS/científico | Excelente | Limitado |

### Conclusión

Para el volumen actual y proyectado a corto plazo, Python es perfectamente suficiente. Go sería relevante principalmente como proxy de transporte puro (sin lógica de dominio), donde el consumo de recursos en una máquina compartida sería la ventaja más concreta.

---

## Escalabilidad: Análisis por Etapas

### Etapa actual / corto plazo: ~50 sesiones simultáneas

- Python no es el cuello de botella a este volumen
- El hardware compartido (CPU/RAM del servidor) es el recurso escaso antes que el runtime
- El riesgo real: operaciones bloqueantes en el event loop de asyncio
- **No se justifica ningún cambio arquitectural**

### Mediano plazo: crecimiento moderado, más robots físicos

El problema principal no será el lenguaje sino la **conexión master única** a rosbridge. Con N robots activos, todos sus mensajes de respuesta llegan mezclados por una sola conexión. El routing por topics (`/robot/r<b32>/response`) lo maneja, pero hay overhead de demultiplexado en la API.

Solución natural: **una conexión WS a rosbridge por robot activo**, no una master. Esto no requiere múltiples instancias de rosbridge, solo múltiples conexiones desde la API.

### Largo plazo: ~1000 sesiones simultáneas

A esa escala el cambio es arquitectural:
- Modelo N:M (N usuarios por M robots) requiere un **hub/multiplexor por robot**
- rosbridge no está diseñado para manejar múltiples clientes, sí para representar un grafo ROS → una instancia por robot es el fit natural
- Separación del proxy de transporte de la lógica de sesión/orquestación
- Se estima que habrá más recursos disponibles para esa etapa

**Nota**: el salto de 50 a 1000 sesiones requerirá cambios arquitecturales independientemente del lenguaje elegido.

---

## Decisión sobre rosbridge: ¿en el servidor o en la Pi?

Durante el análisis se nombraron dos escenarios posibles antes de clarificar cuál era el real:

**Escenario 1** — rosbridge corre *en el robot* (Pi), el monolito se conecta remotamente:
```
Robot: [nodos ROS] ←DDS local→ [rosbridge en Pi]
                                        ↑
                                WS sobre red interna
                                        ↓
Servidor: [API (monolito Python)]
```
DDS queda completamente local a la Pi. El único tráfico que sale del robot es WebSocket sobre un puerto fijo.

**Escenario 2** — rosbridge corre *en el servidor*, los nodos ROS de la Pi se comunican con él via DDS sobre la red:
```
Robot: [nodos ROS] ←DDS sobre red→ Servidor: [rosbridge] ←WS→ [API]
```
DDS tiene que atravesar la red de la facultad, lo cual es problemático (multicast UDP, puertos dinámicos, hostil a firewalls y subredes distintas).

**El setup actual es el Escenario 2**, pero con una diferencia clave respecto a lo que el nombre sugiere: la Pi **no habla DDS directamente**. Habla el protocolo rosbridge (JSON sobre WebSocket), igual que la API. DDS queda confinado dentro del container de rosbridge en el servidor. Por eso el Escenario 2 es más robusto de lo que parecía — ver sección "Topología de Red Real".

El **Escenario 1** sigue siendo la dirección natural a largo plazo (rosbridge en la Pi), pero por razones de escalabilidad con múltiples robots, no por el problema de DDS sobre red.

---

### Topología actual (rosbridge en el servidor)

```
[Pi] ──WS──► [nginx] ──► [rosbridge container, servidor]
                                    ▲
                         [API container, servidor]
```

Ventaja: más simple operacionalmente, todo en un lugar.
Riesgo a escala: con múltiples robots, hay que correr múltiples instancias de rosbridge en el servidor, consumiendo sus recursos.

### Topología alternativa (rosbridge en la Pi)

```
[Pi]
 ├── nodos ROS 2
 ├── rosbridge (container en la Pi)
 └──WS──► [servidor] ──► [API]
```

Ventajas:
- DDS queda completamente local a la Pi (donde debe estar)
- El servidor solo recibe conexiones WS entrantes, no necesita instancias de rosbridge por robot
- Cada robot es autónomo, lleva su bridge consigo
- WS es friendly con cualquier firewall/red
- La Pi inicia la conexión (NAT-friendly)

Desventajas:
- La Pi (Raspberry Pi) necesita cómputo suficiente para rosbridge — **es factible**, tiene Linux
- El servidor necesita un endpoint estable para recibir conexiones de las Pis

Cambio de código necesario: mínimo. `ROSBRIDGE_URL` pasaría de ser fijo a ser dinámico por robot.

**Estado**: no se migra ahora, pero es la dirección natural para cuando haya múltiples robots físicos.

---

## Cambios Aplicables (Priorización)

### ✅ Corto plazo — hacer ahora

**Abstraer la conexión a rosbridge en el módulo realtime.**

Actualmente la lógica habla directamente con la conexión WS master. Envolver eso en una abstracción tipo `RobotChannel`:

```python
# En lugar de hablar directamente con la conexión master:
await master_ws.send(json.dumps({...}))

# Una abstracción que hoy es un wrapper trivial pero es extensible:
await robot_channel.publish(topic, payload, session_id=session.id)
```

`RobotChannel` hoy puede ser un wrapper sobre la conexión master. Cuando se necesite el hub o múltiples conexiones, se cambia la implementación sin tocar el código que la usa. **Es refactor, no reescritura.**

### 🔜 Mediano plazo — cuando haya más robots activos simultáneos

**Una conexión a rosbridge por robot activo.**

No implica múltiples instancias de rosbridge (todavía). Solo múltiples conexiones WS desde la API, una por robot. Esto elimina el demultiplexado de mensajes mezclados y aísla naturalmente los canales.

Requiere que la abstracción `RobotChannel` esté implementada (punto anterior).

### 🔮 Largo plazo — camino a 1000 sesiones

- Hub/multiplexor por robot (fan-out explícito a N usuarios)
- Posible migración de rosbridge a la Pi (una instancia por robot físico)
- Separación del proxy de transporte de la lógica de sesión/orquestación
- Decisión de lenguaje para el proxy (Go sería relevante aquí)
- Recursos adicionales de hardware disponibles para esa etapa

---

## Notas de Diseño Relevantes

- El modelo de sesión actual es **1:1** (un usuario por robot a la vez). El modelo objetivo es **N:M** (N usuarios pueden observar/controlar M robots).
- La relación usuario↔robot está centralizada en un único módulo (el módulo realtime). El mapeo sesión↔robot está encapsulado, lo cual es correcto.
- `robots.user_id` en la DB representa el usuario actualmente asignado al robot (ON DELETE SET NULL).
- Hay un trigger en `robots` que registra automáticamente cada cambio de estado en `robot_status_history`.
- El sistema tiene modo demo completo con mock del robot — toda nueva feature debe mantener compatibilidad.
- La arquitectura usa **Crockford Base32 con prefijo `r`** para los nombres de topics ROS, decisión correcta dado que ROS 2 no permite tokens que empiecen con número.
