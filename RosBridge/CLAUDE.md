# CLAUDE.md — RosBridge

## Descripción General

Servicio que ejecuta [rosbridge_suite](https://github.com/RobotWebTools/rosbridge_suite) como puente WebSocket/JSON entre la API (FastAPI) y el ecosistema ROS 2. Traduce mensajes JSON al protocolo nativo de ROS (DDS).

## Arquitectura

```
API (FastAPI) ──WS:9090──► rosbridge_server ──DDS──► nodos ROS ──► RaspberryPi
```

La API se conecta como cliente WebSocket a rosbridge (puerto 9090) y publica/suscribe topics ROS usando el protocolo JSON de rosbridge.

## Ejecución

```bash
make build                # Construir imagen Docker
make up_demo              # rosbridge + nodo mock (foreground)
make up_dev               # Solo rosbridge (foreground)
make up_demo.detached     # rosbridge + mock (background)
make up_dev.detached      # Solo rosbridge (background)
make down_demo            # Detener demo
make down_dev             # Detener dev
```

Requiere la red Docker `ciie-test` creada previamente (`docker network create ciie-test`).

## Estructura del Código

```
RosBridge/
├── Dockerfile               # ROS Humble + rosbridge_suite + paquetes custom
├── entrypoint.sh            # Sourcear ROS + workspace overlay
├── compose.yaml             # Servicios: rosbridge (dev) y rosbridge-demo (demo)
├── Makefile                 # Comandos unificados
├── config/
│   └── rosbridge_params.yaml   # Configuración de rosbridge (puerto, timeouts, etc.)
├── launch/
│   └── bridge.launch.py     # Launch file: rosbridge + mock opcional (demo:=true)
└── src/
    └── mock_robot/           # Paquete ROS 2 — nodo mock para modo demo
        ├── package.xml
        ├── setup.py
        ├── setup.cfg
        └── mock_robot/
            ├── __init__.py
            └── mock_robot_node.py   # Nodo que simula robots (suscribe commands, publica responses/status)
```

## Docker Compose

Dos servicios con profiles:

| Servicio | Profile | Descripción |
|----------|---------|-------------|
| `rosbridge` | `dev` | Solo rosbridge_server — requiere nodos ROS externos |
| `rosbridge-demo` | `demo` | rosbridge + nodo `mock_robot_node` con robots simulados |

Ambos exponen puerto `9090` y se conectan a la red `ciie-test` con alias `rosbridge`.

## Convención de Topics

Los UUIDs de robots se codifican en **Crockford Base32** para los nombres de topics:

| Topic | Dirección | Contenido |
|-------|-----------|-----------|
| `/robot/<base32>/command` | API → Robot | Comandos JSON-RPC |
| `/robot/<base32>/response` | Robot → API | Respuestas a comandos |
| `/robot/<base32>/status` | Robot → API | Estado periódico del robot |

Tipo de mensaje: `std_msgs/String` con payload JSON.

## Configuración de rosbridge

`config/rosbridge_params.yaml`:
- Puerto: `9090`
- Dirección: `0.0.0.0`
- Tamaño máximo de mensaje: 10 MB
- Retry de arranque: 5s

## Modo Demo

El servicio `rosbridge-demo` lanza el nodo `mock_robot_node` que:
- Lee UUIDs de `DEMO_ROBOT_IDS` (variable de entorno, separados por coma)
- Se suscribe a `/robot/<base32>/command` de cada robot
- Responde con datos simulados en `/robot/<base32>/response`
- Publica estado periódico en `/robot/<base32>/status`

Los UUIDs de demo se configuran en `compose.yaml` → `DEMO_ROBOT_IDS`.

## Protocolo rosbridge (referencia rápida)

### Publicar comando
```json
{
  "op": "publish",
  "topic": "/robot/<base32>/command",
  "msg": { "data": "{\"method\": \"move_arm\", \"params\": {\"angle\": 90}}" }
}
```

### Suscribirse a respuestas/estado
```json
{
  "op": "subscribe",
  "topic": "/robot/<base32>/response",
  "type": "std_msgs/String"
}
```
