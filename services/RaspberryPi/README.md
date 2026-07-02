# RaspberryPi

> [Leer en español](./README.es.md)

Controller that runs on each Raspberry Pi connected to a robot. It registers and authenticates with the central API (FastAPI), then opens a WebSocket directly to the API to receive JSON-RPC 2.0 commands and publish responses/status. Controls the Arduino via serial port.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Running](#running)
- [Environment Variables](#environment-variables)
- [Main Flow](#main-flow)
- [Demo Mode](#demo-mode)

## Architecture

```
                 API (FastAPI)                                        Arduino
                      ▲                                                  ▲
                      │ HTTP (register/handshake) + WS (commands)        │ Serial
                      │                                                  │
┌─────────────────────┴──────────────────────────────────────────────────┴─┐
│                            RaspberryPi (controller)                      │
│  server/ ──register+handshake──►  strategy/remote/ ──commands──► robot/  │
│                                   (ws_strategy)                          │
└──────────────────────────────────────────────────────────────────────────┘
```

1. **Registration & handshake** (HTTP): the Pi registers with the API and obtains a JWT
2. **Commands** (WebSocket directly to the API): the Pi connects to `/m2m/robot/connect` and exchanges JSON-RPC 2.0 messages
3. **Robot control** (Serial): translates JSON-RPC 2.0 commands to serial instructions for the Arduino

## Prerequisites

- Python 3.13.7+
- uv package manager
- Access to the API (local or via Docker network)

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
| `ARDUINO_PORT` | Arduino serial port | (specific USB path) |
| `CREATE_DEFAULT_METADATA` | `1` to auto-generate credentials on startup | `1` |
| `MOCK_ROBOT` | `1` to use mock controller without hardware | `1` |

## Main Flow

### 1. Initialization

1. Loads environment variables (`config.py`)
2. Creates a `ServerServices` instance
3. Tries to load `robot-metadata.json` — if it doesn't exist and `CREATE_DEFAULT_METADATA=1`, generates new credentials (UUID + 24-char random password)

### 2. Registration and connection (self-registration with approval)

1. `register()` — `POST /m2m/robot/register` with `{external_identifier, psw}` (idempotent)
2. `connect_with_retry()` — retries `POST /m2m/robot/handshake` (HTTP Basic) with exponential backoff:
   - 403 → robot pending approval, waits and retries (5s → 10s → 20s... up to 300s max)
   - 200 → handshake successful, returns JWT
   - Other error → log warning + retry with backoff
3. An admin must approve the robot via `POST /admin/robot/{id}/approve` for the handshake to return 200

### 3. Operation (async, WS directly to the API)

1. Enters the robot context manager (opens serial port or mock)
2. `WsStrategy` opens a WebSocket to `/m2m/robot/connect` and authenticates with the JWT
3. Receives JSON-RPC 2.0 commands from the WS, executes them on the robot (serial I/O via `run_in_executor`)
4. Sends responses and periodic status (every 5s) over the same WS

Automatic reconnection with exponential backoff (1s → 30s) if the connection is lost.

## Demo Mode

With `MOCK_ROBOT=1`, the controller uses `robot_mock_controller.py` which simulates the robot's behavior without physical hardware (Arduino/robotic arm). Combined with `CREATE_DEFAULT_METADATA=1`, it allows running the full flow without hardware.
