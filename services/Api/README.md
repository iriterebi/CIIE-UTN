# Api

*Leer en [español](README.es.md).*

FastAPI backend for the Labs Remoto system. Serves as the central entry point for both users and robots.

## What it does

1. **User-facing** — Authentication (JWT), session management, and real-time robot control via WebSocket
2. **Robot-facing** — Self-registration and handshake (M2M). Command communication goes through ROS via RosBridge

## Requirements

- Python 3.13.7+
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL (see `../Db/`)
- RosBridge (see `../RosBridge/`)

## Quick start

```bash
# Install dependencies (from repo root)
uv sync

# Copy and configure environment variables
cp .env.example .env

# Start the development server
make up_dev
```

## Makefile commands

| Command | Description |
|---------|-------------|
| `make up_dev` | Start dev server (`fastapi dev src/server.py`) |
| `make build` | Build Docker image |
| `make up` | Run with Docker Compose (foreground) |
| `make up.detached` | Run with Docker Compose (background) |
| `make down` | Stop Docker Compose services |

## Environment variables

| Variable | Example | Description |
|----------|---------|-------------|
| `POSTGRES_PASSWORD` | `secret` | PostgreSQL password |
| `POSTGRES_USER` | `myuser` | PostgreSQL user |
| `POSTGRES_DB` | `ciie_db` | Database name |
| `POSTGRES_URL` | `db-dev:5432` | PostgreSQL host (no protocol) |
| `ROSBRIDGE_URL` | `ws://rosbridge:9090` | RosBridge WebSocket URL |
| `JWT_SECRET_KEY` | `secret` | Secret for signing JWTs |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token expiration in minutes |

## API routes

| Prefix | Auth | Purpose |
|--------|------|---------|
| `/auth` | Public (except `/me`) | Login, signup, current user, request robot access |
| `/admin/robot` | Admin (WIP — currently unprotected) | Robot CRUD, approve/reject, send commands |
| `/user/robot` | JWT (via WebSocket message) | Real-time user-robot communication |
| `/m2m/robot` | HTTP Basic (internal) | Robot registration and handshake |

## Project structure

```
src/
├── server.py              # Entry point — mounts routers, lifespan manages RosBridgeClient
├── config.py              # Loads and validates env vars (fails on startup if missing)
├── db_connection/         # SQLModel engine + session dependency
├── auth/                  # Authentication module
│   ├── entities/          # User model, AccessToken, EncryptionServiceConfiguration
│   ├── services/          # EncryptionService, UserService, get_current_user
│   ├── repositories/      # (placeholder)
│   └── routes/            # /auth endpoints
└── robot/                 # Robot module
    ├── entities/          # Robot model, DTOs, JSON-RPC commands, errors
    ├── services/          # RobotService, RosBridgeClient, HandshakeService, AccessValidator, UserToRobotCommunication
    ├── repositories/      # RobotRepository — DB access
    ├── routes/            # /admin/robot, /m2m/robot, /user/robot endpoints
    └── utils/             # Crockford Base32 encoding (UUID → ROS topic names)
```

## Tests

```bash
uv run pytest
```

Tests are organized mirroring the `src/` structure under `tests/`.

## Dependencies

- **fastapi[standard]** — Framework + uvicorn + websockets
- **sqlmodel** — ORM (SQLAlchemy + Pydantic)
- **psycopg2-binary** — PostgreSQL driver
- **pyjwt** — JWT encode/decode
- **bcrypt** — Password hashing
- **email-validator** — EmailStr validation
