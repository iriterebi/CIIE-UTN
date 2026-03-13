# RaspberryPi

> [Leer en español](./README.es.md)

Controller that runs on each Raspberry Pi connected to a robot. It registers and authenticates with the central API (FastAPI), then connects to rosbridge via WebSocket to receive ROS commands and publish responses/status. Controls the Arduino via serial port.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Running](#running)
- [Environment Variables](#environment-variables)
- [Main Flow](#main-flow)
- [Demo Mode](#demo-mode)

## Architecture

```
API (FastAPI)                    rosbridge (:9090)                Arduino
     │                               ▲     │                        ▲
     │ HTTP (register/handshake)     │     │ WS (subscribe)        │ Serial
     ▼                               │     ▼                        │
┌─────────────────────────────────────────────────────────────────────┐
│                         RaspberryPi                                 │
│  server/ ──register+handshake──►   rosbridge/ ──commands──► robot/  │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Registration & handshake** (HTTP): the Pi registers with the API and obtains a JWT + topic base (`/robot/r<base32>`)
2. **Commands** (WebSocket via rosbridge): the Pi subscribes to its command topic and publishes responses/status
3. **Robot control** (Serial): translates JSON-RPC 2.0 commands to serial instructions for the Arduino

## Prerequisites

- Python 3.13.7+
- uv package manager
- Access to the API and rosbridge (local or via Docker network)

## Running

```bash
uv run python -m controller
```

Requires `.env` or `.env.defaults` with the environment variables.

## Environment Variables

Defined in `.env.defaults` (defaults), overridden by `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SERVER_URL` | API M2M base URL | `http://localhost:8000/m2m/robot/` |
| `ROSBRIDGE_URL` | rosbridge WebSocket URL | `ws://localhost:9090` |
| `ARDUINO_PORT` | Arduino serial port | (specific USB path) |
| `CREATE_DEFAUL_METADATA` | `1` to auto-generate credentials on startup | `1` |
| `MOCK_ROBOT` | `1` to use mock controller without hardware | `1` |

## Main Flow

### 1. Initialization

1. Loads environment variables (`config.py`)
2. Creates a `ServerServices` instance
3. Tries to load `robot-metadata.json` — if it doesn't exist and `CREATE_DEFAUL_METADATA=1`, generates new credentials (UUID + 24-char random password)

### 2. Registration and connection (self-registration with approval)

1. `register()` — `POST /m2m/robot/register` with `{external_identifier, psw}` (idempotent)
2. `connect_with_retry()` — retries `POST /m2m/robot/handshake` (HTTP Basic) with exponential backoff:
   - 403 → robot pending approval, waits and retries (5s → 10s → 20s... up to 300s max)
   - 200 → handshake successful, returns JWT + topic base
   - Other error → log warning + retry with backoff
3. An admin must approve the robot via `POST /admin/robot/{id}/approve` for the handshake to return 200

### 3. Operation (async, via rosbridge)

1. Enters the robot context manager (opens serial port or mock)
2. `PiRosBridgeClient` connects to rosbridge via WebSocket
3. Subscribes to `/robot/r<base32>/command` to receive JSON-RPC 2.0 commands
4. On receiving a command, executes it on the robot (serial I/O via `run_in_executor`)
5. Publishes the response to `/robot/r<base32>/response`
6. Publishes periodic status (every 5s) to `/robot/r<base32>/status`

Automatic reconnection with exponential backoff (1s → 30s) if the connection is lost.

## Demo Mode

With `MOCK_ROBOT=1`, the controller uses `robot_mock_controller.py` which simulates the robot's behavior without physical hardware (Arduino/robotic arm). Combined with `CREATE_DEFAUL_METADATA=1`, it allows running the full flow without hardware.
