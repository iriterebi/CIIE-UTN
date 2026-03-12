# RosBridge

> [Leer en español](./README.es.md)

Service that runs [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite) as a bridge between the API (FastAPI) and the ROS 2 ecosystem. Exposes a WebSocket server (port 9090) that translates JSON messages to the native ROS protocol.

## Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Running](#running)
- [Topic Convention](#topic-convention)
- [Demo Mode](#demo-mode)
- [rosbridge Protocol](#rosbridge-protocol)

## Architecture

```
API (FastAPI) ──WS:9090──► rosbridge_server ──DDS──► ROS nodes ──► RaspberryPi
```

The API connects as a WebSocket client to rosbridge and publishes/subscribes to ROS topics using a JSON protocol. rosbridge translates these messages to ROS 2's native system (DDS).

## Prerequisites

- Docker and Docker Compose
- Docker network `ciie-test` created (`docker network create ciie-test`)

## Running

```bash
# Build the image
make build

# Dev mode: rosbridge only (requires external ROS nodes)
make up_dev

# Demo mode: rosbridge + mock node that simulates robots
make up_demo

# Background
make up_dev.detached
make up_demo.detached

# Stop
make down_dev
make down_demo
```

Or from the project root Makefile:

```bash
make rosbridge.demo          # Demo mode (foreground)
make rosbridge.up.detached   # Dev mode (background)
```

## Topic Convention

Robot UUIDs are encoded in **Crockford Base32** for use in ROS topic names.

| Topic | Direction | Content |
|-------|-----------|---------|
| `/robot/<base32>/command` | API → Robot | JSON-RPC commands |
| `/robot/<base32>/response` | Robot → API | Command responses |
| `/robot/<base32>/status` | Robot → API | Periodic robot status |

Message type: `std_msgs/String` with JSON payload.

**Example**: UUID `a0e1f2a3-b4c5-d6e7-f8a9-b0c1d2e3f4a5` → Base32 → topic `/robot/A1W3T51ECNQEFSN4P1C3QHRT95/command`

## Demo Mode

The `rosbridge-demo` service (profile `demo`) launches rosbridge alongside a `mock_robot_node` that simulates robots:

- Reads UUIDs from `DEMO_ROBOT_IDS` (environment variable, comma-separated)
- Subscribes to `/robot/<base32>/command` for each robot
- Responds with simulated data on `/robot/<base32>/response`
- Publishes periodic status on `/robot/<base32>/status`

Configurable via `DEMO_ROBOT_IDS` in `compose.yaml`.

## rosbridge Protocol

Example JSON messages the API would send to the rosbridge WebSocket:

### Publish a command

```json
{
  "op": "publish",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/command",
  "msg": {
    "data": "{\"method\": \"move_arm\", \"params\": {\"angle\": 90}}"
  }
}
```

### Subscribe to responses

```json
{
  "op": "subscribe",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/response",
  "type": "std_msgs/String"
}
```

### Subscribe to status

```json
{
  "op": "subscribe",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/status",
  "type": "std_msgs/String"
}
```
