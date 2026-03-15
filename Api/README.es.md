# Api

*Read in [English](README.md).*

Backend FastAPI para el sistema Labs Remoto. Punto de entrada central para usuarios y robots.

## Qué hace

1. **Para usuarios** — Autenticación (JWT), gestión de sesiones y control de robots en tiempo real vía WebSocket
2. **Para robots** — Auto-registro y handshake (M2M). La comunicación de comandos pasa por ROS vía RosBridge

## Requisitos

- Python 3.13.7+
- Gestor de paquetes [uv](https://docs.astral.sh/uv/)
- PostgreSQL (ver `../Db/`)
- RosBridge (ver `../RosBridge/`)

## Inicio rápido

```bash
# Instalar dependencias (desde la raíz del repo)
uv sync

# Copiar y configurar variables de entorno
cp .env.example .env

# Iniciar servidor de desarrollo
make up_dev
```

## Comandos del Makefile

| Comando | Descripción |
|---------|-------------|
| `make up_dev` | Iniciar servidor de desarrollo (`fastapi dev src/server.py`) |
| `make build` | Construir imagen Docker |
| `make up` | Ejecutar con Docker Compose (foreground) |
| `make up.detached` | Ejecutar con Docker Compose (background) |
| `make down` | Detener servicios Docker Compose |

## Variables de entorno

| Variable | Ejemplo | Descripción |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `secret` | Password de PostgreSQL |
| `POSTGRES_USER` | `myuser` | Usuario de PostgreSQL |
| `POSTGRES_DB` | `ciie_db` | Nombre de la base de datos |
| `POSTGRES_URL` | `db-dev:5432` | Host de PostgreSQL (sin protocolo) |
| `ROSBRIDGE_URL` | `ws://rosbridge:9090` | URL WebSocket de RosBridge |
| `JWT_SECRET_KEY` | `secret` | Secret para firmar JWTs |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Expiración del token en minutos |

## Rutas de la API

| Prefijo | Auth | Propósito |
|---------|------|-----------|
| `/auth` | Público (excepto `/me`) | Login, signup, usuario actual, solicitar acceso a robot |
| `/admin/robot` | Admin (WIP — sin protección) | CRUD de robots, aprobación/rechazo, enviar comandos |
| `/user/robot` | JWT (vía mensaje WebSocket) | Comunicación usuario-robot en tiempo real |
| `/m2m/robot` | HTTP Basic (interno) | Registro y handshake de robots |

## Estructura del proyecto

```
src/
├── server.py              # Punto de entrada — monta routers, lifespan gestiona RosBridgeClient
├── config.py              # Carga y valida env vars (falla al iniciar si faltan)
├── db_connection/         # Engine SQLModel + dependencia de sesión
├── auth/                  # Módulo de autenticación
│   ├── entities/          # Modelo User, AccessToken, EncryptionServiceConfiguration
│   ├── services/          # EncryptionService, UserService, get_current_user
│   ├── repositories/      # (placeholder)
│   └── routes/            # Endpoints /auth
└── robot/                 # Módulo de robots
    ├── entities/          # Modelo Robot, DTOs, comandos JSON-RPC, errores
    ├── services/          # RobotService, RosBridgeClient, HandshakeService, AccessValidator, UserToRobotCommunication
    ├── repositories/      # RobotRepository — acceso a DB
    ├── routes/            # Endpoints /admin/robot, /m2m/robot, /user/robot
    └── utils/             # Codificación Crockford Base32 (UUID → nombres de topics ROS)
```

## Tests

```bash
uv run pytest
```

Los tests están organizados espejando la estructura de `src/` bajo `tests/`.

## Dependencias

- **fastapi[standard]** — Framework + uvicorn + websockets
- **sqlmodel** — ORM (SQLAlchemy + Pydantic)
- **psycopg2-binary** — Driver PostgreSQL
- **pyjwt** — JWT encode/decode
- **bcrypt** — Hashing de contraseñas
- **email-validator** — Validación de EmailStr
