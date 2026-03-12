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

La API se conecta como cliente WebSocket a rosbridge y publica/suscribe topics ROS usando un protocolo JSON. rosbridge traduce estos mensajes al sistema nativo de ROS 2 (DDS).

## Prerrequisitos

- Docker y Docker Compose
- Red Docker `ciie-test` creada (`docker network create ciie-test`)

## Ejecución

```bash
# Construir la imagen
make build

# Modo dev: solo rosbridge (requiere nodos ROS externos)
make up_dev

# Modo demo: rosbridge + nodo mock que simula robots
make up_demo

# En background
make up_dev.detached
make up_demo.detached

# Detener
make down_dev
make down_demo
```

O desde el Makefile raíz del proyecto:

```bash
make rosbridge.demo          # Modo demo (foreground)
make rosbridge.up.detached   # Modo dev (background)
```

## Convención de Topics

Los UUIDs de los robots se codifican en **Crockford Base32** para usarlos en los nombres de topics ROS.

| Topic | Dirección | Contenido |
|-------|-----------|-----------|
| `/robot/<base32>/command` | API → Robot | Comandos JSON-RPC |
| `/robot/<base32>/response` | Robot → API | Respuestas a comandos |
| `/robot/<base32>/status` | Robot → API | Estado periódico del robot |

Tipo de mensaje: `std_msgs/String` con payload JSON.

**Ejemplo**: UUID `a0e1f2a3-b4c5-d6e7-f8a9-b0c1d2e3f4a5` → Base32 → topic `/robot/A1W3T51ECNQEFSN4P1C3QHRT95/command`

## Modo Demo

El servicio `rosbridge-demo` (profile `demo`) levanta rosbridge junto con un nodo `mock_robot_node` que simula robots:

- Lee UUIDs de `DEMO_ROBOT_IDS` (variable de entorno, separados por coma)
- Se suscribe a `/robot/<base32>/command` de cada robot
- Responde con datos simulados en `/robot/<base32>/response`
- Publica estado periódico en `/robot/<base32>/status`

Configurable via `DEMO_ROBOT_IDS` en `compose.yaml`.

## Protocolo rosbridge

Ejemplos de mensajes JSON que la API enviaría al WebSocket de rosbridge:

### Publicar un comando

```json
{
  "op": "publish",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/command",
  "msg": {
    "data": "{\"method\": \"move_arm\", \"params\": {\"angle\": 90}}"
  }
}
```

### Suscribirse a respuestas

```json
{
  "op": "subscribe",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/response",
  "type": "std_msgs/String"
}
```

### Suscribirse a estado

```json
{
  "op": "subscribe",
  "topic": "/robot/A1W3T51ECNQEFSN4P1C3QHRT95/status",
  "type": "std_msgs/String"
}
```
