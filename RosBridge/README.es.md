# RosBridge

> [Read in English](./README.md)

Servicio que ejecuta [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite) como puente entre la API (FastAPI) y el ecosistema ROS 2. Expone un servidor WebSocket (puerto 9090) que traduce mensajes JSON al protocolo nativo de ROS.

## Índice

- [Arquitectura](#arquitectura)
- [Prerrequisitos](#prerrequisitos)
- [Ejecución](#ejecución)
- [Convención de Topics](#convención-de-topics)
- [Modo Demo](#modo-demo)
- [Protocolo rosbridge](#protocolo-rosbridge)

## Arquitectura

```
API (FastAPI) ──WS:9090──► rosbridge_server ──DDS──► nodos ROS ──► RaspberryPi
```

La API y la RaspberryPi se conectan como clientes WebSocket a rosbridge y publican/suscriben topics ROS usando un protocolo JSON. rosbridge traduce estos mensajes al sistema nativo de ROS 2 (DDS).

## Prerrequisitos

- Docker y Docker Compose
- Red Docker `ciie-test` creada (`docker network create ciie-test`)

## Ejecución

```bash
# Construir la imagen
make build

# Ejecutar rosbridge (foreground)
make up

# Ejecutar rosbridge (background)
make up.detached

# Detener
make down
```

## Convención de Topics

Los UUIDs de los robots se codifican en **Crockford Base32** con prefijo `r` para usarlos en los nombres de topics ROS (ROS 2 no permite tokens que empiecen con número).

| Topic | Dirección | Contenido |
|-------|-----------|-----------|
| `/robot/r<base32>/command` | API → Robot | Comandos JSON-RPC 2.0 |
| `/robot/r<base32>/response` | Robot → API | Respuestas JSON-RPC 2.0 (con `id`) |
| `/robot/r<base32>/status` | Robot → API | Notifications JSON-RPC 2.0 (sin `id`, `method: "status.update"`) |

Tipo de mensaje: `std_msgs/String` con payload JSON-RPC 2.0.

## Modo Demo

Para probar sin hardware físico, ejecutar el controlador RaspberryPi en modo mock (`MOCK_ROBOT=1`) conectado a rosbridge. Ver `RaspberryPi/CLAUDE.md` para detalles.

## Protocolo rosbridge

Ejemplos de mensajes JSON enviados al WebSocket de rosbridge:

### Advertise de un topic (antes de publicar)

```json
{
  "op": "advertise",
  "topic": "/robot/r<base32>/command",
  "type": "std_msgs/String"
}
```

### Publicar un comando

```json
{
  "op": "publish",
  "topic": "/robot/r<base32>/command",
  "msg": {
    "data": "{\"jsonrpc\":\"2.0\",\"method\":\"move_arm\",\"params\":{\"angle\":90},\"id\":1}"
  }
}
```

### Suscribirse a respuestas

```json
{
  "op": "subscribe",
  "topic": "/robot/r<base32>/response",
  "type": "std_msgs/String"
}
```

### Suscribirse a estado

```json
{
  "op": "subscribe",
  "topic": "/robot/r<base32>/status",
  "type": "std_msgs/String"
}
```
