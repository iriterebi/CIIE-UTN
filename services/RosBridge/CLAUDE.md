# CLAUDE.md — RosBridge

## Descripción General

Servicio que ejecuta [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite) como puente WebSocket/JSON entre la API (FastAPI) y el ecosistema ROS 2. Traduce mensajes JSON al protocolo nativo de ROS (DDS).

## Arquitectura

```
API (FastAPI) ──WS:9090──► rosbridge_server ──DDS──► nodos ROS ──► RaspberryPi
```

La API y la RaspberryPi se conectan como clientes WebSocket a rosbridge (puerto 9090) y publican/suscriben topics ROS usando el protocolo JSON de rosbridge.

## Ejecución

```bash
make build            # Construir imagen Docker
make up               # Ejecutar rosbridge (foreground)
make up.detached      # Ejecutar rosbridge (background)
make down             # Detener rosbridge
```

Requiere la red Docker `ciie-test` creada previamente (`docker network create ciie-test`).

## Estructura del Código

```
RosBridge/
├── Dockerfile               # ROS Humble + rosbridge_suite
├── entrypoint.sh            # Sourcear ROS
├── compose.yaml             # Servicio rosbridge
├── Makefile                 # Comandos unificados
├── config/
│   └── rosbridge_params.yaml   # Configuración de rosbridge (puerto, timeouts, etc.)
└── launch/
    └── bridge.launch.py     # Launch file: rosbridge_server
```

## Convención de Topics

Los UUIDs de robots se codifican en **Crockford Base32** con prefijo `r` para los nombres de topics (ROS 2 no permite tokens que empiecen con número):

| Topic | Dirección | Contenido |
|-------|-----------|-----------|
| `/robot/r<base32>/command` | API → Robot | Comandos JSON-RPC 2.0 |
| `/robot/r<base32>/response` | Robot → API | Respuestas JSON-RPC 2.0 (con `id`) |
| `/robot/r<base32>/status` | Robot → API | Notifications JSON-RPC 2.0 (sin `id`, `method: "status.update"`) |

Tipo de mensaje: `std_msgs/String` con payload JSON-RPC 2.0.

## Configuración de rosbridge

`config/rosbridge_params.yaml`:
- Puerto: `9090`
- Dirección: `0.0.0.0`
- Tamaño máximo de mensaje: 10 MB
- Retry de arranque: 5s

## Modo Demo

Para pruebas sin hardware, ejecutar la RaspberryPi en modo mock (`MOCK_ROBOT=1`) conectada a rosbridge. Ver `../RaspberryPi/CLAUDE.md` para detalles.

## Protocolo rosbridge (referencia rápida)

### Advertise (antes de publicar)
```json
{
  "op": "advertise",
  "topic": "/robot/r<base32>/command",
  "type": "std_msgs/String"
}
```

### Publicar comando
```json
{
  "op": "publish",
  "topic": "/robot/r<base32>/command",
  "msg": { "data": "{\"jsonrpc\":\"2.0\",\"method\":\"move_arm\",\"params\":{\"angle\":90},\"id\":1}" }
}
```

### Suscribirse a respuestas/estado
```json
{
  "op": "subscribe",
  "topic": "/robot/r<base32>/response",
  "type": "std_msgs/String"
}
```
