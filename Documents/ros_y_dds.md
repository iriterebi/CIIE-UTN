# ROS, DDS y rosbridge — Conceptos y Arquitectura de Comunicación

## Índice

- [ROS (Robot Operating System)](#ros-robot-operating-system)
  - [Qué es](#qué-es)
  - [Concepto central: nodos y topics](#concepto-central-nodos-y-topics)
  - [Otros patrones de comunicación](#otros-patrones-de-comunicación)
  - [ROS 1 vs ROS 2](#ros-1-vs-ros-2)
  - [Herramientas principales](#herramientas-principales)
- [DDS (Data Distribution Service)](#dds-data-distribution-service)
  - [Qué es](#qué-es-1)
  - [Cómo funciona](#cómo-funciona)
  - [QoS (Quality of Service)](#qos-quality-of-service)
  - [DDS vs un broker tradicional](#dds-vs-un-broker-tradicional)
  - [Implementaciones](#implementaciones)
  - [Relación ROS 2 — DDS](#relación-ros-2--dds)
- [rosbridge_suite](#rosbridge_suite)
  - [Qué es](#qué-es-2)
  - [Protocolo rosbridge](#protocolo-rosbridge)
  - [rosbridge NO es un broker](#rosbridge-no-es-un-broker)
- [Arquitectura de comunicación del proyecto](#arquitectura-de-comunicación-del-proyecto)
  - [Flujo de un comando completo](#flujo-de-un-comando-completo)
  - [Convención de topics por robot](#convención-de-topics-por-robot)
  - [Despliegue con Docker](#despliegue-con-docker)
  - [Cambios necesarios en la API](#cambios-necesarios-en-la-api)
  - [Modo demo](#modo-demo)
  - [Contrato entre equipos](#contrato-entre-equipos)

---

## ROS (Robot Operating System)

### Qué es

ROS es un framework open-source para desarrollo de software robótico. A pesar del nombre, **no es un sistema operativo** — es un middleware que corre sobre Linux (principalmente Ubuntu).

Resuelve el problema de coordinar muchos componentes de un robot (sensores, motores, cámaras, planificación de movimiento, comunicación) proporcionando una infraestructura estándar para que se comuniquen entre sí sin acoplarse directamente.

### Concepto central: nodos y topics

- **Nodo**: un proceso independiente que hace una tarea específica (leer un sensor, mover un motor, procesar imagen)
- **Topic**: un canal de mensajes con nombre. Los nodos **publican** o **se suscriben** a topics
- **Mensaje**: estructura de datos tipada que viaja por un topic

```
[Nodo Cámara] ──publica→ topic "/camera/image" ──suscribe→ [Nodo Visión]
[Nodo Visión] ──publica→ topic "/detected_object" ──suscribe→ [Nodo Control]
[Nodo Control] ──publica→ topic "/motor/cmd" ──suscribe→ [Nodo Motor]
```

Los nodos no se conocen entre sí — solo conocen los topics. Esto permite reemplazar, agregar o quitar nodos sin tocar el resto.

### Otros patrones de comunicación

- **Services**: request/response síncrono (como una llamada HTTP)
- **Actions**: tareas de larga duración con feedback intermedio (ej: "ve al punto X" con actualizaciones de progreso)

### ROS 1 vs ROS 2

- **ROS 1** (2007): usaba un nodo central "master" que coordinaba todo. Si el master caía, todo caía
- **ROS 2** (2017+, el que usa este proyecto con **Humble**): descentralizado, usa DDS (Data Distribution Service) como capa de comunicación. Mejor soporte para tiempo real, seguridad y multi-robot

### Herramientas principales

- **colcon**: sistema de build (compila los paquetes)
- **ament**: sistema de packaging (metadata de dependencias)
- **rclpy** / **rclcpp**: client libraries para Python y C++
- **ros2 run/launch**: ejecutar nodos individuales o conjuntos

---

## DDS (Data Distribution Service)

### Qué es

Es un **estándar abierto** (de la OMG — Object Management Group, los mismos de UML) para comunicación pub/sub en sistemas distribuidos. Existe desde 2004, mucho antes de ROS 2.

Resuelve el problema de que muchos procesos (potencialmente en muchas máquinas) se envíen datos entre sí de forma rápida y confiable, sin un servidor central que coordine todo.

### Cómo funciona

#### Descubrimiento automático

Cuando un nodo DDS arranca, se anuncia en la red ("existo, publico X, me suscribo a Y"). Los otros nodos lo descubren automáticamente. No hay broker, no hay master, no hay registro central.

```
Nodo A arranca → multicast: "publico /robot/cmd"
Nodo B arranca → multicast: "me suscribo a /robot/cmd"
DDS conecta A→B automáticamente (peer-to-peer)
```

Si A se cae, B lo detecta. Si C aparece publicando lo mismo, B recibe de ambos.

#### Topics tipados

La comunicación se organiza en topics. En DDS los tipos están definidos con IDL (Interface Definition Language) y se serializan en binario — mucho más eficiente que JSON.

### QoS (Quality of Service)

La característica estrella de DDS. Se puede configurar **por topic** cómo se comporta la comunicación:

| QoS Policy | Qué controla | Ejemplo |
|---|---|---|
| **Reliability** | ¿Garantiza entrega? | `RELIABLE` (retransmite si se pierde) vs `BEST_EFFORT` (no retransmite) |
| **Durability** | ¿Guarda mensajes para suscriptores futuros? | `TRANSIENT_LOCAL` (sí, los últimos N) vs `VOLATILE` (no) |
| **History** | ¿Cuántos mensajes mantiene en buffer? | `KEEP_LAST(10)` vs `KEEP_ALL` |
| **Deadline** | ¿Cada cuánto debe llegar un mensaje? | "Si no recibo en 100ms, algo falló" |
| **Liveliness** | ¿Cómo detecto que un nodo cayó? | Heartbeats automáticos |
| **Lifespan** | ¿Cuánto tiempo es válido un mensaje? | "Después de 5s, descártalo" |

Esto permite en un mismo sistema tener:
- Comandos de motor con `RELIABLE` + `DEADLINE(50ms)` — no puede fallar ni retrasarse
- Streaming de cámara con `BEST_EFFORT` — si se pierde un frame, no importa
- Estado del robot con `TRANSIENT_LOCAL` — un nodo nuevo recibe el último estado conocido al conectarse

### DDS vs un broker tradicional

| | DDS | Broker (RabbitMQ, Kafka, MQTT) |
|---|---|---|
| **Arquitectura** | Descentralizado (peer-to-peer) | Centralizado (broker es SPOF) |
| **Descubrimiento** | Automático (multicast) | Manual (te conectas al broker) |
| **Punto de falla** | Ninguno central | Si el broker cae, cae todo |
| **QoS** | Muy granular (20+ policies) | Básico (at-most-once, at-least-once) |
| **Latencia** | Muy baja (directo entre nodos) | Mayor (pasa por el broker) |
| **Serialización** | Binaria (CDR), tipada | Depende (JSON, Protobuf, etc.) |
| **Uso típico** | Robótica, defensa, IoT industrial | Web, microservicios, streaming |

### Implementaciones

DDS es un estándar, no un software. Hay varias implementaciones:

- **Fast DDS** (eProsima) — la default de ROS 2 Humble, open source
- **Cyclone DDS** (Eclipse) — alternativa popular en ROS 2, más ligera
- **RTI Connext** — comercial, usado en defensa y aviación

ROS 2 permite elegir cuál usar cambiando una variable de entorno:

```bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp    # Fast DDS (default)
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp  # Cyclone DDS
```

### Relación ROS 2 — DDS

```
┌─────────────────────────────────┐
│          Tu código              │
│     (Python con rclpy)          │
├─────────────────────────────────┤
│       RCL (ROS Client Library)  │  ← API de ROS 2
├─────────────────────────────────┤
│       RMW (middleware)          │  ← adaptador
├─────────────────────────────────┤
│       DDS (Fast/Cyclone/RTI)    │  ← transporte real
└─────────────────────────────────┘
```

ROS 2 es esencialmente una **capa de abstracción sobre DDS**. Simplifica:
- Los tipos de mensajes (`.msg` en vez de IDL)
- El build system (colcon/ament en vez de DDS tooling)
- Las convenciones (namespaces, nodos, launch files)
- El ecosistema (paquetes de robótica, visualización, simulación)

Pero por debajo, cuando un nodo ROS 2 publica un mensaje, DDS es el que lo transporta.

---

## rosbridge_suite

### Qué es

rosbridge_suite es un meta-paquete oficial de ROS que contiene tres componentes:

1. **rosbridge_library** — la lógica core: traduce entre JSON y mensajes ROS internos
2. **rosbridge_server** — el servidor que expone esa lógica via WebSocket (puerto default: `9090`)
3. **rosapi** — un servicio ROS que permite consultar metadata (listar topics, tipos de mensajes, etc.)

Cuando se levanta rosbridge_server, se obtiene un servidor WebSocket al que cualquier cliente puede conectarse y operar con el grafo de ROS sin tener ROS instalado.

### Protocolo rosbridge

Es un protocolo JSON sobre WebSocket. Cada mensaje tiene un campo `op` (operación):

#### Publicar a un topic

```json
{
  "op": "publish",
  "topic": "/robot/rabc123/command",
  "msg": {
    "data": "{\"jsonrpc\": \"2.0\", \"method\": \"move_arm\", \"params\": {\"angle\": 90}, \"id\": 1}"
  }
}
```

#### Suscribirse a un topic

```json
{
  "op": "subscribe",
  "id": "sub_001",
  "topic": "/robot/rabc123/status",
  "type": "std_msgs/String"
}
```

A partir de ahí, rosbridge envía mensajes por el mismo WebSocket:

```json
{
  "op": "publish",
  "topic": "/robot/rabc123/status",
  "msg": {
    "data": "ready"
  }
}
```

#### Desuscribirse

```json
{
  "op": "unsubscribe",
  "id": "sub_001",
  "topic": "/robot/rabc123/status"
}
```

#### Llamar un service

```json
{
  "op": "call_service",
  "id": "call_001",
  "service": "/robot/rabc123/get_position",
  "args": {}
}
```

Respuesta:

```json
{
  "op": "service_response",
  "id": "call_001",
  "values": {"x": 1.0, "y": 2.5, "z": 0.3},
  "result": true
}
```

### rosbridge NO es un broker

Se parece a un broker en que recibe mensajes de un lado y los entrega al otro, y hace traducción de protocolo. Pero un broker clásico (RabbitMQ, Kafka, MQTT) tiene:

- **Colas/persistencia** — guarda mensajes si el receptor no está disponible. rosbridge no guarda nada
- **Garantías de entrega** — at-least-once, exactly-once, etc. rosbridge no tiene esto
- **Routing propio** — el broker decide a quién va cada mensaje. rosbridge solo traduce; el routing lo hace DDS

rosbridge es un **protocol translator** (traductor de protocolo) entre el mundo WebSocket/JSON y el mundo ROS/DDS. El verdadero sistema de mensajería es DDS.

```
API ──JSON/WS──► [rosbridge: traductor] ──► [DDS: el sistema de mensajería real] ──► nodos ROS
```

---

## Arquitectura de comunicación del proyecto

La decisión de diseño para Labs Remoto es usar **rosbridge_suite** como hub de comunicación en tiempo real. Tanto la API como la RaspberryPi se conectan como clientes WebSocket a rosbridge — ninguno tiene ROS instalado, solo hablan WebSocket/JSON con rosbridge.

```
┌──────────┐     HTTP/WS      ┌──────────┐      WS (9090)     ┌────────────────┐
│ Frontend │◄────────────────►│   API    │◄───────────────────►│  rosbridge     │
│          │                   │ (FastAPI)│                      │  _server       │
└──────────┘                   └──────────┘                      └───────┬────────┘
                                                                        │ WS (9090)
                                                    ┌───────────────────┼───────────────────┐
                                                    │                   │                   │
                                              ┌─────┴──────┐     ┌─────┴──────┐     ┌──────┴──────┐
                                              │ RaspberryPi │     │ RaspberryPi │     │ RaspberryPi │
                                              │     A       │     │     B       │     │     C       │
                                              └─────┬───────┘     └─────┬───────┘     └──────┬──────┘
                                                    │ Serial            │ Serial             │ Serial
                                              ┌─────┴──────┐     ┌─────┴──────┐     ┌──────┴──────┐
                                              │  Arduino A  │     │  Arduino B  │     │  Arduino C  │
                                              └─────────────┘     └─────────────┘     └─────────────┘
```

### Flujo de un comando completo

```
1. Usuario envía comando via WebSocket a la API
   → {"jsonrpc": "2.0", "method": "move_arm", "params": {"angle": 90}, "id": 1}

2. API valida auth, permisos y acceso al robot

3. API publica al topic del robot via rosbridge
   → WS a rosbridge: {"op": "publish", "topic": "/robot/r<base32>/command", "msg": {"data": "<json-rpc>"}}

4. rosbridge traduce el JSON a mensaje ROS y lo publica al topic DDS

5. La RaspberryPi del robot está conectada a rosbridge como cliente WS,
   suscrita a /robot/r<base32>/command
   → Recibe el mensaje JSON-RPC 2.0

6. RaspberryPi ejecuta el comando en el Arduino (vía serial)

7. La respuesta hace el camino inverso:
   RaspberryPi → publish /robot/r<base32>/response → rosbridge → API → Usuario
```

### Convención de topics por robot

Los UUIDs de robots se codifican en **Crockford Base32** con prefijo `r` para los nombres de topics (ROS 2 no permite tokens que empiecen con número):

```
/robot/r<base32>/command    ← comandos hacia el robot (JSON-RPC 2.0 request)
/robot/r<base32>/response   ← respuestas a comandos (JSON-RPC 2.0 response, con id)
/robot/r<base32>/status     ← estado del robot (JSON-RPC 2.0 notification, sin id)
```

Tipo de mensaje: `std_msgs/String` con payload JSON-RPC 2.0. Cada robot tiene su propio set de topics.

### Despliegue con Docker

rosbridge se levanta como un contenedor más en la red `ciie-test`, usando un Dockerfile propio con rosbridge pre-instalado:

```bash
cd RosBridge
make build        # Construir imagen
make up           # Ejecutar (foreground)
make up.detached  # Ejecutar (background)
```

### Modo demo

Para el modo demo sin hardware:

- **rosbridge corriendo** — es solo software, no necesita hardware (`make rosbridge.up`)
- **RaspberryPi en modo mock** — con `MOCK_ROBOT=1` y `CREATE_DEFAUL_METADATA=1`, la Pi se auto-registra, hace handshake con la API, se conecta a rosbridge y simula respuestas del robot sin comunicación serial

### Contrato entre equipos

El acuerdo entre el equipo de la API y el equipo de ROS se limita a:

1. **Nombres de topics**: patrón acordado (`/robot/r<base32>/command`, `/robot/r<base32>/status`, `/robot/r<base32>/response`)
2. **Formato de mensajes**: JSON-RPC 2.0 dentro del `std_msgs/String`
3. **Puerto de rosbridge**: host y puerto donde estará disponible (default: `9090`)
4. **Red Docker**: rosbridge accesible en la red `ciie-test`
