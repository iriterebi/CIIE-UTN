# CLAUDE.md — Labs Remoto

## Descripción General

Proyecto universitario (CIIE) para el control remoto de robots en laboratorios. Los usuarios se conectan a través de un frontend web, interactúan con un backend Python (FastAPI), que se comunica directamente con cada robot vía WebSocket. Cada robot corre en una Raspberry Pi que gestiona el hardware (Arduino + servos) y opcionalmente componentes ROS 2 locales.

## Arquitectura

```
[Frontend] ←WS→ [API (FastAPI)] ←WS→ [RaspberryPi] → [Arduino/Robot]
                       ↕                    ↕
                  [PostgreSQL]      [ROS 2 / DDS local (opcional)]
```

- **services/WebClient/**: Frontend Vue 3 + TypeScript + PicoCSS — SPA servida con nginx
- **services/Api/**: Backend FastAPI — punto de entrada principal al sistema. Maneja auth, sesiones, comunicación WebSocket con usuarios y conexión WebSocket directa con cada Pi (sin intermediarios)
- **services/RaspberryPi/**: Corre en cada robot. Se auto-registra en la API y mantiene un WebSocket directo a `/m2m/robot/connect` para recibir comandos y publicar respuestas/estado. Controla el Arduino vía serial (o mock en modo demo)
- **services/Arduino/**: Firmware nativo del brazo robótico (control de 7 servos)
- **services/Db/**: Esquema PostgreSQL 17.5, migraciones (dbmate) y datos semilla
- **services/Proxy/**: Configuración de nginx como reverse proxy principal. En dev se instala en el host; en prod corre containerizado via quadlet. Punto de entrada para todo el tráfico — proxea la SPA, API y rutas WS, restringe rutas internas (`/m2m`) a intranet
- **packages/**: Paquetes compartidos entre servicios (vacío por ahora)
- **quadlets/**: Configuración de deploy de producción con Podman Quadlets. Incluye archivos `.container`, `.network`, `.volume` y el script `deploy.sh` para compilar localmente y desplegar via SSH
- **ros_tryouts/**: Workspace ROS 2 experimental del otro equipo. **No tocar** — solo referencia
- **Documents/**: Documentación general del sistema, investigaciones cerradas

### Rol de ROS 2 (importante)

ROS 2 **no es** el bus de comunicación API↔robot. Tras el refactor en `raspi-arqui-refactor`, ROS 2 quedó como **IPC interno del robot dentro de la Raspi** (coordina componentes locales como `ros2_serial_agent` que habla con el Arduino). Si se usa, debe ser una *local strategy* en la Pi, no un transporte remoto. **No proponer** strategies `ros2://` ni puentes API↔ROS.

## Stack Tecnológico

- **Lenguaje**: Python 3.13.7+ (Api, RaspberryPi), Arduino C++ (firmware)
- **Framework**: FastAPI con SQLModel ORM
- **Base de datos**: PostgreSQL 17.5 (Alpine)
- **Autenticación**: JWT (HS256) + bcrypt para hashing de contraseñas
- **Tiempo real**: WebSockets (usuario↔API y API↔Pi, sin intermediarios)
- **Protocolo**: JSON-RPC 2.0 para comandos (también en el Unix socket CLI↔core en la Pi)
- **Gestor de paquetes**: uv (workspace: Api + RaspberryPi)
- **Despliegue**: Docker Compose (dev), Podman Quadlets (prod)
- **Migraciones**: dbmate

## Estructura del Proyecto

```
├── services/                 # Servicios y subproyectos
│   ├── Api/                  # Backend FastAPI (activo, WIP)
│   │   ├── src/
│   │   │   ├── server.py     # Punto de entrada, monta los routers
│   │   │   ├── config.py     # Carga de variables de entorno
│   │   │   ├── auth/         # Auth JWT, servicio de usuarios, encriptación
│   │   │   ├── robot/        # Rutas robot, WS, handshake, adapters, pipe usuario↔robot
│   │   │   └── db_connection/
│   │   ├── COMUNICACION.md   # Arquitectura del pipe usuario↔robot (StreamSource, excepciones)
│   │   ├── Makefile          # `make up_dev` → fastapi dev src/server.py
│   │   └── pyproject.toml
│   ├── RaspberryPi/          # Controlador del lado del robot (activo, micro core + strategies)
│   │   ├── controller/       # Runtime del robot (proceso principal)
│   │   │   ├── main.py       # Registry, factory, arranca el core
│   │   │   ├── config.py     # Pydantic Settings
│   │   │   ├── core.py       # MicroCore: enruta + socket server + handlers
│   │   │   ├── socket_server.py  # Unix socket JSON-RPC 2.0 (dispatch async)
│   │   │   ├── type_defs.py  # TypedDicts compartidos (importado por cli/)
│   │   │   ├── json_rpc.py   # Modelos pydantic + handler JSON-RPC 2.0
│   │   │   ├── strategy/     # ABC Strategy + registry
│   │   │   │   ├── base.py             # ABC Strategy (State enum) + LocalStrategy
│   │   │   │   ├── registry.py
│   │   │   │   ├── local/              # serial_strategy.py, mock_strategy.py
│   │   │   │   └── remote/ws_strategy.py  # único remoto: WS directo a /m2m/robot/connect
│   │   │   ├── server/       # Registro + handshake HTTP con la API
│   │   │   └── robot/        # Controladores serial (real + mock)
│   │   ├── cli/              # CLI de gestión (proceso separado, habla por Unix socket)
│   │   │   ├── __init__.py   # Cáscara: from .cli import main
│   │   │   ├── __main__.py   # Entry: python -m cli
│   │   │   └── cli.py        # Contenido (monolítico hoy, split pendiente)
│   │   ├── ARQUITECTURA.md   # Fuente de verdad: micro core + strategies + etapas refactor
│   │   └── pyproject.toml
│   ├── Db/                   # Base de datos (activo)
│   │   ├── def/migrations/   # Migraciones de esquema
│   │   ├── seed/migrations/  # Datos semilla
│   │   ├── compose.yaml      # Servicios de DB (dev, ephemeral, dbmate)
│   │   └── Makefile          # make migrate_db, make seed_apply, etc.
│   ├── Proxy/                # nginx reverse proxy (activo)
│   │   ├── nginx.conf        # Config para instalación en host (dev/legacy)
│   │   ├── nginx.container.conf  # Config para contenedor (producción)
│   │   └── Dockerfile        # nginx:alpine con config de producción
│   ├── WebClient/            # Frontend Vue 3 + TypeScript + PicoCSS (activo)
│   └── Arduino/              # Firmware del robot (activo)
├── packages/                 # Paquetes compartidos (vacío por ahora)
├── quadlets/                 # Deploy de producción con Podman Quadlets (activo)
│   ├── *.container           # Definición de cada servicio
│   ├── *.network, *.volume   # Red y volúmenes
│   └── deploy.sh             # Script: build local → transfer SSH → reload
├── ros_tryouts/              # Workspace ROS 2 (activo, no tocar — otro equipo)
├── Documents/                # Documentación e investigaciones
├── compose.yaml              # Compose raíz (incluye Db + WebClient)
└── pyproject.toml            # Raíz del workspace uv
```

> **Nota**: `services/RosBridge/` y su quadlet fueron eliminados en `raspi-arqui-refactor`. Si aparecen referencias residuales (env vars `ROSBRIDGE_URL`, alias `rosbridge` en alguna red, `/rosbridge/` en nginx), son vestigios — limpiarlos.

## Setup de Desarrollo

### Prerrequisitos

- Python 3.13.7+
- Gestor de paquetes uv
- Docker y Docker Compose

### Ejecutar la API

```bash
cd services/Api && make up_dev
# o: fastapi dev src/server.py
```

### Base de Datos

```bash
cd services/Db
make up_db.dev              # Iniciar PostgreSQL (foreground)
make up_db.dev.detached     # Iniciar PostgreSQL (background)
make migrate_db             # Ejecutar migraciones
make seed_apply             # Aplicar datos semilla
```

La DB efímera (`make up_db.ephimeral`) usa tmpfs — los datos se pierden al detener. Útil para testing.

### Ejecutar la RaspberryPi (controlador)

```bash
cd services/RaspberryPi
uv run python -m controller   # Runtime del robot
uv run python -m cli          # CLI de gestión (proceso separado, Unix socket)
```

En modo demo se usa `MOCK_ROBOT=1` y se evita serial real. La conexión remota usa `WsStrategy` por defecto (WebSocket directo a `/m2m/robot/connect`).

### Variables de Entorno Requeridas

**Api:**
- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_URL`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

**RaspberryPi** (`.env.defaults` tiene valores por defecto):
- `SERVER_URL` — endpoint de la API (default: `http://localhost:8000/m2m/robot/`). La `WsStrategy` deriva `ws://`/`wss://` desde aquí
- `ARDUINO_PORT` — puerto serial
- `MOCK_ROBOT` — `1` para usar controlador mock
- `CREATE_DEFAULT_METADATA` — `1` para auto-generar credenciales del robot
- `METADATA_FILE` — ruta al archivo de credenciales (default: `./robot-metadata.json`)

### Red Docker

```bash
docker network create ciie-test  # Requerido antes del primer docker compose up
```

## Mapa de Rutas de la API

| Prefijo | Auth | Propósito |
|---------|------|-----------|
| `/auth` | Público | Login, signup, usuario actual, solicitar acceso a robot |
| `/admin/robot` | Admin (WIP — actualmente sin protección) | CRUD robots, aprobación/rechazo |
| `/user/robot` | JWT (vía WebSocket) | Comunicación usuario↔robot en tiempo real |
| `/m2m/robot` | HTTP Basic + JWT (vía WS) | Registro + handshake HTTP; conexión persistente vía WS en `/m2m/robot/connect` |

## Esquema de Base de Datos

- **usuarios**: id, nombrecompleto, email, usr_name, usr_psw, statuss (enum: profe/alumno), usr_pronouns, Accion
- **robots**: id (UUID), external_identifier, name (nullable), description, psw, status (CHECK: `pending_approval`, `approved`, `rejected`, `disabled`), user_id (FK → usuarios)
- **robot_status_history**: Registro automático de auditoría mediante trigger en la tabla robots

## Flujo de Comunicación

### Registro y aprobación de robots (self-registration)

1. **Robot se auto-registra**: La Pi arranca, genera credenciales (`robot-metadata.json`) y llama a `POST /m2m/robot/register` con `external_identifier` + `psw`. El robot se crea en DB con `status=pending_approval` y `name=null`
2. **Robot espera aprobación**: La Pi reintenta `POST /m2m/robot/handshake` con backoff exponencial. Recibe 403 mientras no esté aprobado
3. **Admin aprueba**: `POST /admin/robot/{id}/approve` con `name` y `description` → cambia status a `approved`
4. **Robot se conecta vía WS**: El siguiente handshake retorna un JWT. La Pi abre WebSocket a `/m2m/robot/connect`, recibe el challenge `{method: "send_credentials"}`, envía `{token: <JWT>}` y la API responde `{status: "success auth"}`. La conexión es 1:1 por robot, con reconexión y backoff 1s→30s

El registro es idempotente: si el `external_identifier` ya existe, retorna el robot existente sin error. El endpoint `/register` es interno (accesible solo por intranet, protegido vía proxy).

### Operación

1. **Usuario se conecta**: Abre WebSocket en `/user/robot/send_command` → envía mensaje de auth en 10s → envía comandos JSON-RPC 2.0
2. **API enruta directo a la Pi**: El `UsersXRobotMapType` (pipe) conecta `UserConnection`↔`RobotConnection` bidireccionalmente con `TaskGroup`. Las validaciones de payload viven en `UserStreamSource`. La API no transforma datos: cada adapter traduce su protocolo ↔ formato interno
3. **La Pi ejecuta y responde**: Recibe JSON-RPC por su WS, lo procesa con la strategy activa (serial real, mock, o local en el futuro) y devuelve respuesta/estado por el mismo WS

## Convenciones del proyecto

- **Documentación**: siempre en español
- **READMEs**: siempre en dos versiones — `README.md` (inglés) y `README.es.md` (español), cada uno referenciando al otro
- **Nombres de carpetas**: las carpetas principales de subproyectos van en PascalCase (ej: `Api/`, `Db/`, `RaspberryPi/`)
- **Docker**: todo el proyecto debe poder ejecutarse con Docker/Docker Compose. Cada subproyecto tiene su propio Dockerfile (si necesario) y docker-compose.yaml
- **Modo demo**: el proyecto debe poder ejecutarse completo sin hardware físico (mock de RaspberryPi/robot). Garantizar compatibilidad con modo demo en toda nueva feature
- **Makefiles**: todos los subproyectos usan Makefile como punto de entrada unificado para comandos, incluso si son redundantes con otras herramientas
- **Código**: comentarios en español o inglés
- **Campos de DB**: en español (`nombrecompleto`, `statuss`, `usr_name`)
- **Roles**: `'profe'` = admin, `'alumno'` = usuario regular
- **Auth de robots**: external_identifier (UUID string) + password, almacenado en `robot-metadata.json` en cada Pi
- **Workspace uv**: ejecutar `uv sync` desde la raíz para instalar todas las dependencias
- **Herramientas de desarrollo**: autopep8 (formateo), mypy (type checking), pylint (linting)

## Convenciones de código (refactor `raspi-arqui-refactor`)

- **`__init__.py` minimal**: al convertir un módulo `foo.py` en paquete `foo/`, el código va en un archivo nombrado dentro del paquete (ej. `foo/foo.py` o `foo/main.py`). `__init__.py` queda como cáscara con re-exports; `__main__.py` como entry point
- **Validaciones siempre en el adapter** correspondiente (ej. `UserStreamSource` para mensajes de usuario), nunca en `StreamConnection`, en el pipe `UsersXRobotMapType` ni en el orquestador. El pipe debe ser agnóstico al contenido
- **`RobotConnection` persiste entre pipes**: cleanup asimétrico — el usuario cierra el WS, el robot persiste. No poner cleanup genérico en `StreamConnection.connect()`; usar template method `_on_disconnect`

## Decisiones arquitectónicas vigentes

- **API↔Pi: WebSocket directo, sin rosbridge**. RosBridge fue eliminado (servicio, quadlet, env vars, código cliente y adapters). Investigación que cerró la decisión: `Documents/ros_tl_investigation/compendio_labs_remoto.md` (sección "Decisión: rclpy directo en la Pi")
- **ROS 2 = IPC interno del robot** en la Raspi (ver §Rol de ROS 2). No proponer strategies `ros2://` ni puentes API↔ROS
- **Un proceso, dos threads en la Pi** (cuando se integre rclpy): `rclpy.spin` en daemon thread, asyncio en main thread
- **Core enrutador puro**: no transforma datos; cada adapter traduce su protocolo ↔ formato interno
- **Dos strategies intercambiables en la Pi**: local (ROS 2 / serial / mock) y remoto (WS / MQTT / HTTP). Único strategy remoto registrado hoy: `WsStrategy`
- **CLI de la Pi = proceso separado** (Unix socket + JSON-RPC 2.0). **No usar Typer** — el CLI es async y los scoped args por strategy se resuelven mejor con `argparse` + subparsers + `nargs=REMAINDER`. Investigación cerrada en `Documents/cli_typer_investigacion.md` (reconsiderar solo si se cierra issue #950 de Typer o si aparece otro CLI similar en el repo)
- **Pipe 1:1 (API)**: un usuario por robot; N:M queda para el futuro
- **State enum** (`running`/`paused`/`stopped`): pause/resume **no** abstractos en la ABC. `LocalStrategy` extiende `Strategy` con `set_telemetry` + `get_telemetry_enabled` abstractos
- **Handlers parametrizados** por `Side` enum, registrados con `partial`

## Documentos clave a consultar

- **`services/RaspberryPi/ARQUITECTURA.md`** — fuente de verdad sobre micro core + strategies + etapas del refactor en la Pi
- **`services/Api/COMUNICACION.md`** — arquitectura del pipe usuario↔robot, `StreamSource`, excepciones `UserSideClosed` / `RobotSideClosed`
- **`Documents/ros_tl_investigation/compendio_labs_remoto.md`** — justificación del abandono de rosbridge (rclpy directo)
- **`Documents/cli_typer_investigacion.md`** — decisión cerrada sobre Typer (no adoptar)
- **`tmp/handoff.proyecto.md`** y **`tmp/handoff.quadlets.md`** (si existen) — handoffs activos entre sesiones (estado del refactor, deuda técnica, sesiones de deploy abiertas)
