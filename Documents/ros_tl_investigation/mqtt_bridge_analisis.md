# MQTT Bridge: Análisis de Implementación para Labs Remoto
> Evaluación de mqtt_client vs nodo custom para reemplazar rosbridge como transporte

---

## Contexto

Continuación del análisis en [topologias_ros_multi_robot.md](topologias_ros_multi_robot.md). Se eligió **MQTT** como patrón de transporte para reemplazar rosbridge. Este documento analiza cómo implementar el bridge entre ROS 2 (en la Pi) y la API (FastAPI) a través de un broker MQTT.

ROS es requerido en la Pi por decisión técnica/política del equipo — el equipo del robot usa ROS y está trabajando en una plataforma externa de pruebas. Además, el tipado nativo de mensajes ROS (`JointState`, `JointTrajectory`, etc.) es una ganancia futura cuando se adopte.

---

## Estructura de datos actual

Hoy los mensajes viajan como `std_msgs/String` con payload JSON-RPC 2.0:

**Comando** (API → Robot):
```json
{"jsonrpc": "2.0", "method": "move_arm", "params": {"joint": 1, "angle": 45}, "id": 1}
```

**Respuesta** (Robot → API):
```json
{"jsonrpc": "2.0", "result": {"status": "ok", "method": "move_arm"}, "id": 1}
```

**Status** (Robot → API, periódico):
```json
{"jsonrpc": "2.0", "method": "status.update", "params": {"connected": true, "battery": 85}}
```

Con MQTT, esta misma estructura viaja como payload MQTT string. La API hace `json.loads(payload)`, el robot hace `json.loads(msg.data)`. **No cambia el formato, solo el transporte.**

---

## Opción 1: `mqtt_client` (paquete oficial de ROS 2)

Paquete C++ mantenido por ika-rwth-aachen. Disponible vía `apt install` para Humble, Jazzy, Kilted, Rolling.

### Dos modos de operación

**Modo no-primitivo (default)** — para comunicación ROS ↔ ROS vía MQTT:
- Serializa mensajes como **CDR binario** (serialización nativa de ROS 2)
- El payload MQTT es opaco — un cliente no-ROS (como FastAPI con paho-mqtt) **no puede leerlo**
- **No sirve para nuestro caso** porque la API no tiene ROS

**Modo primitivo** — para clientes no-ROS:
- Convierte `std_msgs` primitivos a **string plano**
- La conversión es directa:

| ROS msg | `data` | Payload MQTT |
|---|---|---|
| `std_msgs/String` | `"{"jsonrpc":"2.0",...}"` | `{"jsonrpc":"2.0",...}` |
| `std_msgs/Int32` | `42` | `42` |
| `std_msgs/Bool` | `true` | `true` |
| `std_msgs/Float32` | `3.14` | `3.140000` |

Nuestro JSON-RPC dentro de `std_msgs/String` **pasa transparente** en modo primitivo.

### Configuración

Los topics se mapean en YAML estático:

```yaml
/**/*:
  ros__parameters:
    broker:
      host: mosquitto
      port: 1883
    bridge:
      ros2mqtt:  # ROS → MQTT (respuestas del robot)
        ros_topics:
          - /robot/rABCDEFG/response
        /robot/rABCDEFG/response:
          mqtt_topic: robot/rABCDEFG/response
          primitive: true
      mqtt2ros:  # MQTT → ROS (comandos de la API)
        mqtt_topics:
          - robot/rABCDEFG/command
        robot/rABCDEFG/command:
          ros_topic: /robot/rABCDEFG/command
          primitive: true
```

### Problema: topics estáticos vs robots dinámicos

Nuestros robots se registran dinámicamente con UUIDs en Crockford Base32 (`/robot/r<base32>/command`). Con `mqtt_client`:

1. **Pre-configurar todos los robots** — no factible, los UUIDs son dinámicos
2. **Llamar servicios ROS en runtime** (`~/new_ros2mqtt_bridge`, `~/new_mqtt2ros_bridge`) — viable pero agrega complejidad, requiere otro nodo que maneje el ciclo de vida
3. **Reiniciar el nodo con nueva config** — frágil, interrumpe bridges existentes

### Parámetros disponibles

| Parámetro | Default | Descripción |
|---|---|---|
| `broker.host` | `localhost` | Hostname del broker MQTT |
| `broker.port` | `1883` | Puerto del broker |
| `broker.user` | (vacío) | Usuario para auth |
| `broker.pass` | (vacío) | Password para auth |
| `broker.tls.enabled` | `false` | Usar SSL/TLS |
| `client.buffer.size` | `0` | Buffer de mensajes offline |
| `client.clean_session` | `true` | Sesión limpia |
| `client.keep_alive_interval` | `60.0` | Keep-alive en segundos |
| `bridge.ros2mqtt.*.primitive` | `false` | Modo primitivo |
| `bridge.ros2mqtt.*.ros_type` | (auto) | Forzar tipo de mensaje ROS |
| `bridge.ros2mqtt.*.advanced.mqtt.qos` | `0` | QoS MQTT (0, 1, 2) |
| `bridge.ros2mqtt.*.advanced.ros.qos.reliability` | `auto` | `auto`/`reliable`/`best_effort` |
| `bridge.ros2mqtt.*.advanced.ros.qos.durability` | `auto` | `auto`/`volatile`/`transient_local` |

---

## Opción 2: Nodo custom ROS 2 + paho-mqtt (recomendada)

Un nodo Python ROS 2 simple que usa `paho-mqtt` directamente y crea bridges dinámicamente:

```python
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import paho.mqtt.client as mqtt

class MqttBridge(Node):
    def __init__(self):
        super().__init__('mqtt_bridge')
        self.mqtt = mqtt.Client()
        self.mqtt.connect("mosquitto", 1883)
        self.mqtt.on_message = self._on_mqtt
        self.mqtt.loop_start()
        self._pubs = {}   # mqtt_topic → ros publisher
        self._subs = {}   # ros_topic → ros subscription

    def bridge_robot(self, robot_b32: str):
        """Se llama cuando un robot se registra y es aprobado."""
        # Robot → API: respuestas/status ROS van a MQTT
        for suffix in ('response', 'status'):
            ros_topic = f'/robot/{robot_b32}/{suffix}'
            mqtt_topic = f'robot/{robot_b32}/{suffix}'
            self.create_subscription(
                String, ros_topic,
                lambda msg, t=mqtt_topic: self.mqtt.publish(t, msg.data),
                10)

        # API → Robot: comandos MQTT van a ROS
        mqtt_topic_cmd = f'robot/{robot_b32}/command'
        ros_topic_cmd = f'/robot/{robot_b32}/command'
        self.mqtt.subscribe(mqtt_topic_cmd)
        pub = self.create_publisher(String, ros_topic_cmd, 10)
        self._pubs[mqtt_topic_cmd] = pub

    def _on_mqtt(self, client, userdata, msg):
        """Recibe comando de la API vía MQTT, lo publica en ROS."""
        pub = self._pubs.get(msg.topic)
        if pub:
            ros_msg = String()
            ros_msg.data = msg.payload.decode()
            pub.publish(ros_msg)
```

### Por qué es más práctico para nuestro caso

- **Topics dinámicos**: `bridge_robot()` se llama cuando un robot completa el handshake
- **Control total**: sin config YAML estática, sin reiniciar nodos
- **~50 líneas de código**: simple de entender y mantener
- **El mismo `std_msgs/String` con JSON-RPC** que ya se usa
- **Sin dependencia de paquete externo**: solo `rclpy` + `paho-mqtt` (ambos ya disponibles)

---

## Comparativa

| | `mqtt_client` (paquete) | Nodo custom + paho-mqtt |
|---|---|---|
| Topics dinámicos | No (YAML estático o servicios ROS) | Sí (programático) |
| Complejidad | Media | Baja (~50 LOC) |
| Tipos soportados para non-ROS | Solo primitivos | Lo que se decida |
| Mantenimiento | ika-rwth-aachen | Nuestro equipo |
| Fit con arquitectura dinámica | Parcial | Directo |
| Reconexión | Configurable | Hay que implementarla |
| Auth/TLS | Configurable vía YAML | Hay que configurarla en código |

---

## Flujo propuesto con MQTT

```
[Browser] ──WS──► [API + paho-mqtt] ──MQTT──► [Mosquitto]
                        |                          │
                   [PostgreSQL]          ┌─────────┼─────────┐
                                         ▼         ▼         ▼
                                     [Pi 1]    [Pi 2]    [Pi 3]
                                   MqttBridge  MqttBridge  MqttBridge
                                   (nodo custom)
                                       ↕ ROS topics locales
                                   [nodos ROS]
                                       ↕
                                   [Arduino]
```

### Topics MQTT (misma convención que los topics ROS, sin `/` inicial)

| Topic MQTT | Dirección | Contenido |
|---|---|---|
| `robot/r<base32>/command` | API → Robot | JSON-RPC 2.0 comando |
| `robot/r<base32>/response` | Robot → API | JSON-RPC 2.0 respuesta |
| `robot/r<base32>/status` | Robot → API | JSON-RPC 2.0 notificación de estado |

### Qué cambia vs el setup actual

| Aspecto | Hoy (rosbridge) | Con MQTT |
|---|---|---|
| Transporte servidor↔robot | WebSocket (protocolo rosbridge) | MQTT |
| Broker/relay | rosbridge en el servidor | Mosquitto en el servidor |
| Conexión de la API | Una WS master a rosbridge | Cliente MQTT a Mosquitto |
| Conexión de la Pi | Cliente WS a rosbridge | Nodo ROS + paho-mqtt local |
| Formato de mensajes | JSON-RPC en `std_msgs/String` | JSON-RPC en `std_msgs/String` (sin cambio) |
| Auth/TLS | No | Sí (nativo MQTT) |
| QoS / garantía de entrega | No | Sí (3 niveles) |
| Buffering ante desconexión | No | Sí |
| Dependencia de ROS en servidor | Sí (container rosbridge) | No (solo Mosquitto) |

---

## Preguntas abiertas

1. **¿El nodo MqttBridge corre en la Pi o en el servidor?** Lo natural es en la Pi (cada robot es autónomo). El servidor solo tiene Mosquitto + la API.

2. **¿Cómo se enteran los nodos ROS locales de la Pi de que hay un nuevo bridge?** El nodo MqttBridge corre en la misma Pi, comparte el grafo ROS local. Los nodos del robot ya publican/suscriben a `/robot/r<base32>/*` — el bridge simplemente los conecta al broker MQTT.

3. **¿Cuándo se activa el bridge de un robot?** Después del handshake exitoso. La Pi recibe su topic base y el nodo MqttBridge llama a `bridge_robot(robot_b32)`.

4. **¿Se necesita rosbridge todavía?** No en el servidor. Opcionalmente en la Pi para debugging local (roslibjs, visualización web del grafo ROS), pero no en el path de producción.

---

## Referencias

- [mqtt_client (GitHub)](https://github.com/ika-rwth-aachen/mqtt_client)
- [Eclipse Paho MQTT Python](https://github.com/eclipse/paho.mqtt.python)
- [Eclipse Mosquitto](https://mosquitto.org/)
- [MQTT en micro-ROS (EMQX)](https://www.emqx.com/en/blog/mqtt-and-micro-ros)
