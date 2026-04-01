# Topologías ROS 2 para Sistemas Multi-Robot con Control Remoto Web
> Análisis de patrones estándar y evaluación para Labs Remoto

---

## Contexto

El sistema actual usa **un único rosbridge en el servidor** como punto central de comunicación. Tanto la API como cada RaspberryPi se conectan a él como clientes WebSocket. DDS queda confinado dentro del container de rosbridge — no cruza la red.

El problema: rosbridge está siendo usado como **broker de mensajes** entre múltiples robots y la API, algo para lo que no fue diseñado.

```
[Browser] ──WS──► [API FastAPI] ──WS (master única)──► [rosbridge :9090]
                       |                                  ▲
                  [PostgreSQL]                       WS (por robot)
                                                    /       |       \
                                               [Pi 1]   [Pi 2]   [Pi 3]

Todos los mensajes de todos los robots pasan por UNA conexión.
DDS queda confinado dentro del container de rosbridge.
```

La pregunta es: **¿cuál es la topología estándar para este tipo de ecosistema?**

---

## rosbridge: para qué fue diseñado

rosbridge es un **traductor de protocolo**, no un broker. Su caso de uso canónico:

```
[Browser con roslibjs] ──WS──► [rosbridge] ──DDS──► [nodos ROS locales]
```

Un cliente web habla con **un** grafo ROS local. No fue pensado para rutear mensajes entre múltiples robots, ni para actuar como intermediario central de una flota.

### Problemas conocidos de rosbridge bajo carga multi-robot

- **CPU-bound**: El servidor es muy intensivo en CPU al rutear muchos mensajes. Tornado WebSocket masking es cuello de botella
- **Slowdowns y hangs**: Reportes de lentitud y cuelgues después de ~30 min de uso intenso (issue #765, sin solución)
- **Protocol delay**: Sleep de 10ms por defecto entre mensajes salientes, multiplicado por número de clientes
- **Sin buffering**: Si la conexión se pierde, los mensajes se pierden
- **Sin auth/TLS**: No tiene autenticación ni cifrado nativo
- **JSON overhead**: Serialización JSON ineficiente para datos grandes

---

## Principio común a todas las topologías estándar

Independientemente de la tecnología, todos los patrones bien diseñados comparten un principio:

> **Cada robot es una isla ROS autónoma. La comunicación con el exterior pasa por un bridge WAN-friendly que corre en el robot.**

```
[Robot]                              [Servidor]
┌─────────────────────┐              ┌──────────────┐
│ ROS 2 (DDS local)   │              │              │
│    ↕                 │   WAN/LAN   │   API/Web    │
│ Bridge (WS/MQTT/    │──────────────│              │
│  Zenoh/custom)      │  protocolo   │              │
│                     │  ligero      │              │
└─────────────────────┘              └──────────────┘
```

DDS **nunca** cruza la red entre robot y servidor en un sistema bien diseñado.

---

## Patrones evaluados

### 1. MQTT Bridge — el más natural para nuestra arquitectura

```
[Browser] ──WS──► [API FastAPI] ──MQTT──► [Broker Mosquitto]
                       |                    /       |       \
                  [PostgreSQL]         [Pi+mqtt]  [Pi+mqtt]  [Pi+mqtt]
                                       ROS 2      ROS 2      ROS 2
                                      (local)    (local)    (local)
```

Cada Pi corre `mqtt_client` (paquete oficial de ROS 2, `apt install`) que bridgea sus topics locales al broker MQTT. La API habla MQTT con `paho-mqtt` (Python puro, sin dependencia de ROS). DDS queda completamente local a cada Pi.

**Qué es**: MQTT es el protocolo estándar de IoT para dispositivos remotos reportando a un servidor central. Mosquitto es un broker ligero (~5MB en Alpine).

**Por qué encaja**:
- La API ya es el punto central de coordinación — MQTT es exactamente este patrón
- `paho-mqtt` es Python puro, sin dependencia de ROS en el servidor
- Soporta auth, TLS, QoS (at-most-once, at-least-once, exactly-once)
- Funciona a través de NAT sin problemas
- Buffering de mensajes cuando hay desconexión
- Ecosistema masivo: dashboards, herramientas de monitoreo

**Costo**: agregar Mosquitto como servicio + `mqtt_client` en cada Pi + reemplazar la conexión WS a rosbridge por un cliente MQTT en la API.

**Estado de madurez**: Production-ready. `mqtt_client` es paquete oficial de ROS 2, mantenido por ika-rwth-aachen. Soporte para Humble, Iron, Jazzy, Rolling.

---

### 2. Zenoh Bridge — si se necesita transparencia de topics ROS entre robots

```
[Pi + zenoh-bridge]  ──tcp──►  [Zenoh Router (servidor)]  ◄──tcp──  [Pi + zenoh-bridge]
     ROS 2 local                        │                              ROS 2 local
                                  [API via zenoh-python]
```

`zenoh-bridge-ros2dds` corre en cada Pi, descubre los topics DDS locales y los expone vía Zenoh (protocolo binario eficiente) a un router central. Namespace automático por robot. La API puede hablar Zenoh con `eclipse-zenoh` (librería Python).

Existen dos variantes (NO interoperables entre sí):
- **zenoh-bridge-ros2dds**: Bridge externo que convierte DDS ↔ Zenoh. Se usa con cualquier RMW DDS
- **rmw_zenoh**: Middleware nativo que reemplaza DDS completamente. Incluido desde ROS 2 Jazzy/Kilted, aún experimental

**Por qué encaja**:
- Si los robots necesitaran verse entre sí (coordinación), Zenoh lo da gratis
- Protocolo binario más eficiente que JSON
- Rate-limiting y filtrado de topics configurable
- NAT traversal vía router cloud
- Routers redundantes para alta disponibilidad

**Por qué probablemente no lo necesitamos**:
- Nuestros robots no se comunican entre sí, todo pasa por la API
- Agrega complejidad que no se aprovecha
- Curva de aprendizaje nueva
- La API necesitaría un zenoh client Python (`eclipse-zenoh` en PyPI) o un bridge local

**Estado de madurez**: zenoh-bridge-ros2dds es production-ready (688+ commits, Docker images, paquetes Debian). rmw_zenoh es experimental.

---

### 3. DDS Discovery Server — no aplica a nuestro caso

Solo centraliza el descubrimiento de nodos, pero el transporte de datos sigue siendo DDS peer-to-peer. No resuelve el problema de NAT/firewall entre la Pi y el servidor — necesitaría VPN además. No ayuda con la comunicación web→robot (la API aún necesitaría un bridge como rosbridge).

**Para qué sirve**: redes donde multicast DDS no funciona o es ineficiente (VPNs, WiFi congestionadas, flotas donde el discovery O(N²) es prohibitivo). Específico de Fast DDS.

**Estado**: Production-ready, parte oficial de Fast DDS. Pero no resuelve nuestro problema.

---

### 4. Open-RMF — overkill

Framework completo de gestión de flotas: asignación de tareas, gestión de tráfico, resolución de conflictos, integración con infraestructura de edificios. Pensado para flotas autónomas en hospitales/almacenes, no para teleoperación de brazos desde un navegador.

**Estado**: Production-ready (hospitales, aeropuertos, almacenes), pero extremadamente sobredimensionado para nuestro caso.

---

## Tabla Comparativa

| Criterio | MQTT Bridge | Zenoh Bridge | DDS Discovery Server | Open-RMF | rosbridge (actual) |
|---|---|---|---|---|---|
| **Complejidad de setup** | Baja-Media | Media | Baja | Muy Alta | Ya implementado |
| **Funciona por Internet/NAT** | Sí (nativo) | Sí (router mode) | No (necesita VPN) | Depende | No (necesita LAN) |
| **API puede comunicarse sin ROS** | Sí (`paho-mqtt`) | Sí (`eclipse-zenoh`) | No | No | Sí (WS JSON) |
| **Overhead de protocolo** | Bajo (binario) | Bajo (binario) | N/A (DDS nativo) | DDS nativo | Alto (JSON) |
| **Rendimiento bajo carga** | Bueno | Excelente | Excelente (solo discovery) | Excelente | Pobre |
| **Escalabilidad (robots)** | 1000+ | 100+ | 1000+ (solo discovery) | 100+ | ~10 (con degradación) |
| **Auth/TLS** | Sí (MQTT 5.0) | Sí | No nativo | Sí | No |
| **QoS / garantía de entrega** | Sí (3 niveles) | Sí | N/A | Sí | No |
| **Buffering ante desconexión** | Sí | Sí | N/A | Sí | No |
| **Requiere ROS en el servidor** | No | No | Sí | Sí | Sí |
| **Production-ready** | Sí | Sí | Sí | Sí (pero overkill) | Parcial |

---

## Análisis del setup actual: ¿necesitamos rosbridge?

La cadena actual de comunicación revela algo interesante:

```
API ──WS/rosbridge protocol──► rosbridge ──DDS──► (nada, DDS no sale del container)
Pi  ──WS/rosbridge protocol──► rosbridge ──DDS──► (nada, DDS no sale del container)
```

rosbridge está haciendo de **relay JSON entre dos clientes WebSocket**, con DDS como intermediario innecesario dentro del container. No hay nodos ROS nativos que hablen DDS fuera de ese container.

### Opción A: mover rosbridge a la Pi (propuesta del compendio)

```
API ──WS──► rosbridge (en Pi) ──DDS local──► nodos ROS (en Pi)
```

Válido, pero se sigue dependiendo del protocolo rosbridge (JSON verbose, sin auth, sin QoS) para la comunicación WAN.

### Opción B: reemplazar rosbridge por MQTT

```
API ──MQTT──► Mosquitto ──MQTT──► Pi ──(mqtt_client)──► nodos ROS locales
```

Elimina rosbridge del servidor. La Pi corre ROS 2 + mqtt_client localmente. La API habla MQTT puro, sin dependencia de ROS.

### Opción C: eliminar ROS del flujo si no es necesario en la Pi

Si la Pi no necesita ROS internamente (solo recibe JSON-RPC y controla serial), no se necesita ningún bridge. La Pi puede hablar directo con la API por WebSocket o MQTT.

**Pregunta abierta**: ¿la Pi realmente usa nodos ROS para su lógica interna, o ROS es solo el bus de transporte? Si es solo transporte, estamos agregando complejidad innecesaria. Si la Pi necesita ROS (porque el equipo que maneja esa parte lo requiere, o por planes futuros de usar MoveIt, Navigation2, etc.), entonces MQTT bridge es el reemplazo natural del transporte WAN.

---

## Conclusión

1. **El uso actual de rosbridge como broker centralizado no es el patrón estándar** — es un uso accidental que funciona a baja escala pero no escala
2. **El patrón estándar es: cada robot = isla ROS autónoma + bridge WAN-friendly local**
3. **MQTT bridge es la opción más natural** para nuestra arquitectura API-céntrica
4. **Zenoh es la segunda opción** si se necesitara comunicación directa entre robots
5. **La decisión depende de si ROS es necesario en la Pi** — si no lo es, el bridge se elimina completamente

---

## Referencias

- [mqtt_client para ROS 2 (GitHub)](https://github.com/ika-rwth-aachen/mqtt_client)
- [zenoh-plugin-ros2dds (GitHub)](https://github.com/eclipse-zenoh/zenoh-plugin-ros2dds)
- [rmw_zenoh (GitHub)](https://github.com/ros2/rmw_zenoh)
- [Fast DDS Discovery Server Tutorial (ROS 2 Humble)](https://docs.ros.org/en/humble/Tutorials/Advanced/Discovery-Server/Discovery-Server.html)
- [Open-RMF (GitHub)](https://github.com/open-rmf)
- [rosbridge_suite (GitHub)](https://github.com/RobotWebTools/rosbridge_suite)
- [rosbridge issue #765 — slowdown/hang](https://github.com/RobotWebTools/rosbridge_suite/issues/765)
- [Programming Multiple Robots with ROS 2 (libro)](https://osrf.github.io/ros2multirobotbook/)
