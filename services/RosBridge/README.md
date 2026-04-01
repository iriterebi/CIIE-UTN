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

The API and RaspberryPi connect as WebSocket clients to rosbridge and publish/subscribe to ROS topics using a JSON protocol. rosbridge translates these messages to ROS 2's native system (DDS).

## Prerequisites

- Docker and Docker Compose
- Docker network `ciie-test` created (`docker network create ciie-test`)

## Running

```bash
# Build the image
make build

# Run rosbridge (foreground)
make up

# Run rosbridge (background)
make up.detached

# Stop
make down
```

## Topic Convention

Robot UUIDs are encoded in **Crockford Base32** with an `r` prefix for use in ROS topic names (ROS 2 does not allow tokens starting with a number).

| Topic | Direction | Content |
|-------|-----------|---------|
| `/robot/r<base32>/command` | API → Robot | JSON-RPC 2.0 commands |
| `/robot/r<base32>/response` | Robot → API | JSON-RPC 2.0 responses (with `id`) |
| `/robot/r<base32>/status` | Robot → API | JSON-RPC 2.0 notifications (no `id`, `method: "status.update"`) |

Message type: `std_msgs/String` with JSON-RPC 2.0 payload.

## Demo Mode

To test without physical hardware, run the RaspberryPi controller in mock mode (`MOCK_ROBOT=1`) connected to rosbridge. See `../RaspberryPi/CLAUDE.md` for details.

## rosbridge Protocol

Example JSON messages sent to the rosbridge WebSocket:

### Advertise a topic (before publishing)

```json
{
  "op": "advertise",
  "topic": "/robot/r<base32>/command",
  "type": "std_msgs/String"
}
```

### Publish a command

```json
{
  "op": "publish",
  "topic": "/robot/r<base32>/command",
  "msg": {
    "data": "{\"jsonrpc\":\"2.0\",\"method\":\"move_arm\",\"params\":{\"angle\":90},\"id\":1}"
  }
}
```

### Subscribe to responses

```json
{
  "op": "subscribe",
  "topic": "/robot/r<base32>/response",
  "type": "std_msgs/String"
}
```

### Subscribe to status

```json
{
  "op": "subscribe",
  "topic": "/robot/r<base32>/status",
  "type": "std_msgs/String"
}
```
