# CLAUDE.md — Labs Remoto

## Descripción General

Proyecto universitario (CIIE) para el control remoto de robots en laboratorios. Los usuarios se conectan a través de un frontend web, interactúan con un backend Python (FastAPI), que se comunica con los robots gestionados mediante ROS.

## Arquitectura

```
[Frontend] → [API (FastAPI)] → [RosBridge] ← [RaspberryPi] → [Arduino/Robot]
                  ↕                  ↕
              [PostgreSQL]      [ROS / DDS]
```

- **WebClient/**: Frontend Vue 3 + TypeScript + PicoCSS — SPA servida con nginx
- **Api/**: Backend FastAPI — punto de entrada principal al sistema. Maneja auth, sesiones, comunicación WebSocket con usuarios, publica/suscribe comandos JSON-RPC a rosbridge
- **RosBridge/**: Servicio rosbridge_suite — puente WebSocket/JSON entre clientes (API y RaspberryPi) y ROS 2
- **ROS** (`ros_tryouts/`): Sistema de control y gestión de robots. No lo modificamos nosotros — lo maneja otro miembro del equipo
- **RaspberryPi/**: Se ejecuta en cada robot. Se registra en la API, luego se conecta a rosbridge para recibir comandos y publicar respuestas/estado. Controla el Arduino vía serial
- **Arduino/**: Firmware nativo del brazo robótico (control de 7 servos)
- **Db/**: Esquema PostgreSQL 17.5, migraciones (dbmate) y datos semilla
- **Proxy/**: Configuración de nginx como reverse proxy principal. Único componente instalado en el host (no Docker). Punto de entrada para todo el tráfico — sirve la SPA, proxea API y RosBridge, maneja TLS, restringe rutas internas (`/m2m`, `/rosbridge`) a intranet
- **Documents/**: Documentación general del sistema

## Stack Tecnológico

- **Lenguaje**: Python 3.13.7+ (Api, RaspberryPi), Arduino C++ (firmware)
- **Framework**: FastAPI con SQLModel ORM
- **Base de datos**: PostgreSQL 17.5 (Alpine)
- **Autenticación**: JWT (HS256) + bcrypt para hashing de contraseñas
- **Tiempo real**: WebSockets (usuario↔API) + ROS 2 vía RosBridge (API↔robot)
- **Protocolo**: JSON-RPC 2.0 para comandos a robots
- **Gestor de paquetes**: uv (workspace: Api + RaspberryPi)
- **Despliegue**: Docker Compose
- **Migraciones**: dbmate

## Estructura del Proyecto

```
├── Api/                  # Backend FastAPI (activo, WIP)
│   ├── src/
│   │   ├── server.py     # Punto de entrada, monta los routers
│   │   ├── config.py     # Carga de variables de entorno
│   │   ├── auth/         # Auth JWT, servicio de usuarios, encriptación
│   │   ├── robot/        # Rutas de robot, WS, handshake, JSON-RPC
│   │   └── db_connection/
│   ├── Makefile          # `make up_dev` → fastapi dev src/server.py
│   └── pyproject.toml
├── RaspberryPi/          # Controlador del lado del robot (activo)
│   ├── controller/
│   │   ├── main.py       # Punto de entrada
│   │   ├── config.py     # Carga de .env
│   │   ├── server/       # Registro y handshake con la API
│   │   ├── rosbridge/    # Cliente WS a rosbridge (comandos JSON-RPC vía ROS)
│   │   └── robot/        # Controlador serial (real + mock)
│   └── pyproject.toml
├── Db/                   # Base de datos (activo)
│   ├── def/migrations/   # Migraciones de esquema
│   ├── seed/migrations/  # Datos semilla
│   ├── compose.yaml      # Servicios de DB (dev, ephemeral, dbmate)
│   └── Makefile          # make migrate_db, make seed_apply, etc.
├── RosBridge/            # rosbridge_suite — puente WS/JSON↔ROS (activo)
│   ├── Dockerfile        # ROS Humble + rosbridge_suite
│   ├── compose.yaml      # Servicio rosbridge
│   ├── launch/           # Launch file ROS 2
│   └── Makefile          # make up, make down, etc.
├── Proxy/                # nginx reverse proxy (activo, instalado en host)
│   └── nginx.conf        # Configuración de producción
├── Arduino/              # Firmware del robot (activo)
├── ros_tryouts/          # Workspace ROS 2 (activo, no tocar)
├── Documents/            # Documentación
├── WebClient/            # Frontend Vue 3 + TypeScript + PicoCSS (activo)
├── compose.yaml          # Compose raíz (incluye Db + WebClient + RosBridge)
└── pyproject.toml        # Raíz del workspace uv
```

## Setup de Desarrollo

### Prerrequisitos

- Python 3.13.7+
- Gestor de paquetes uv
- Docker y Docker Compose

### Ejecutar la API

```bash
cd Api && make up_dev
# o: fastapi dev src/server.py
```

### Base de Datos

```bash
cd Db
make up_db.dev              # Iniciar PostgreSQL (foreground)
make up_db.dev.detached     # Iniciar PostgreSQL (background)
make migrate_db             # Ejecutar migraciones
make seed_apply             # Aplicar datos semilla
```

La DB efímera (`make up_db.ephimeral`) usa tmpfs — los datos se pierden al detener. Útil para testing.

### RosBridge

```bash
cd RosBridge
make build                # Construir imagen Docker
make up                   # Ejecutar rosbridge (foreground)
make up.detached          # Ejecutar rosbridge (background)
make down                 # Detener rosbridge
```

Expone WebSocket en `ws://localhost:9090`. Los topics ROS usan UUIDs codificados en Crockford Base32 con prefijo `r`: `/robot/r<base32>/command`, `/robot/r<base32>/response`, `/robot/r<base32>/status`. El prefijo `r` es necesario porque ROS 2 no permite tokens que empiecen con número.

### Variables de Entorno Requeridas

**Api:**
- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_URL`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`

**RaspberryPi** (`.env.defaults` tiene valores por defecto):
- `SERVER_URL` — endpoint de la API (default: `http://localhost:8000/m2m/robot/`)
- `ROSBRIDGE_URL` — URL WebSocket de rosbridge (default: `ws://localhost:9090`)
- `ARDUINO_PORT` — puerto serial
- `MOCK_ROBOT` — `1` para usar controlador mock
- `CREATE_DEFAULT_METADATA` — `1` para auto-generar credenciales del robot

### Red Docker

```bash
docker network create ciie-test  # Requerido antes del primer docker compose up
```

## Mapa de Rutas de la API

| Prefijo | Auth | Propósito |
|---------|------|-----------|
| `/auth` | Público | Login, signup, usuario actual, solicitar acceso a robot |
| `/admin/robot` | Admin (WIP — actualmente sin protección) | CRUD robots, aprobación/rechazo, enviar comandos |
| `/user/robot` | JWT (vía WebSocket) | Comunicación usuario↔robot en tiempo real |
| `/m2m/robot` | HTTP Basic (interno) | Registro y handshake (la comunicación de comandos pasa por ROS vía RosBridge) |

## Esquema de Base de Datos

- **usuarios**: id, nombrecompleto, email, usr_name, usr_psw, statuss (enum: profe/alumno), usr_pronouns, Accion
- **robots**: id (UUID), external_identifier, name (nullable), description, psw, status (CHECK: `pending_approval`, `approved`, `rejected`, `disabled`), user_id (FK → usuarios)
- **robot_status_history**: Registro automático de auditoría mediante trigger en la tabla robots

## Flujo de Comunicación

### Registro y aprobación de robots (self-registration)

1. **Robot se auto-registra**: La Pi arranca, genera credenciales (`robot-metadata.json`) y llama a `POST /m2m/robot/register` con `external_identifier` + `psw`. El robot se crea en DB con `status=pending_approval` y `name=null`
2. **Robot espera aprobación**: La Pi reintenta `POST /m2m/robot/handshake` con backoff exponencial. Recibe 403 mientras no esté aprobado
3. **Admin aprueba**: `POST /admin/robot/{id}/approve` con `name` y `description` → cambia status a `approved`
4. **Robot se conecta**: El siguiente intento de handshake retorna JWT + topic base (`/robot/r<base32>`) → la Pi se conecta a rosbridge y se suscribe a su topic de comandos

El registro es idempotente: si el `external_identifier` ya existe, retorna el robot existente sin error. El endpoint `/register` es interno (accesible solo por intranet, protegido vía proxy).

### Operación

1. **Usuario se conecta**: Abre WebSocket en `/user/robot/send_command` → envía mensaje de auth en 10s → envía comandos JSON-RPC 2.0
2. **La API publica a ROS**: Recibe comandos del usuario, valida acceso, los publica al topic ROS del robot vía RosBridge (`ws://rosbridge:9090`). Las respuestas del robot llegan por ROS y se rutean de vuelta al usuario vía `asyncio.Queue`
3. **La Pi escucha de ROS**: Está suscrita a su topic de comandos en rosbridge. Al recibir un comando JSON-RPC, lo ejecuta en el robot y publica la respuesta/estado en los topics correspondientes

## Convenciones

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
