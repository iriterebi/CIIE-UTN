# Testing y Debugging en ROS 2 — Herramientas para inspeccionar, publicar y monitorear

## Índice

- [CLI de ROS 2 — El `curl` de ROS](#cli-de-ros-2--el-curl-de-ros)
  - [Comandos principales](#comandos-principales)
  - [Comparación con herramientas web](#comparación-con-herramientas-web)
- [Herramientas gráficas](#herramientas-gráficas)
  - [rqt — Suite de plugins Qt](#rqt--suite-de-plugins-qt)
  - [Foxglove Studio — El más moderno](#foxglove-studio--el-más-moderno)
- [Aplicación al proyecto Labs Remoto](#aplicación-al-proyecto-labs-remoto)
  - [Opción 1: CLI dentro del contenedor RosBridge](#opción-1-cli-dentro-del-contenedor-rosbridge)
  - [Opción 2: Foxglove Studio (sin ROS instalado)](#opción-2-foxglove-studio-sin-ros-instalado)
  - [Opción 3: Cualquier cliente WebSocket](#opción-3-cualquier-cliente-websocket)
- [Resumen: qué usar cuándo](#resumen-qué-usar-cuándo)

---

## CLI de ROS 2 — El `curl` de ROS

Vienen instalados con ROS 2 y funcionan desde la terminal. Son la forma más directa de inspeccionar y testear.

### Comandos principales

```bash
# Listar todos los topics activos (como ver todas las rutas de una API)
ros2 topic list

# Ver mensajes en tiempo real (como curl a un SSE/WebSocket)
ros2 topic echo /robot/rabc123/command

# Publicar un mensaje a un topic (como curl -X POST)
ros2 topic pub /robot/rabc123/command std_msgs/String \
  '{"data": "{\"jsonrpc\":\"2.0\",\"method\":\"ping\",\"id\":1}"}'

# Ver frecuencia de mensajes (como un monitor de requests/segundo)
ros2 topic hz /robot/rabc123/status

# Info de un topic (tipo de mensaje, publishers, subscribers)
ros2 topic info /robot/rabc123/command --verbose

# Listar services
ros2 service list

# Llamar un service (como curl a un endpoint HTTP)
ros2 service call /some_service std_srvs/srv/SetBool '{"data": true}'

# Listar nodos activos
ros2 node list

# Ver info de un nodo (topics que publica/suscribe, services que ofrece)
ros2 node info /rosbridge

# Ver schema de un tipo de mensaje
ros2 interface show std_msgs/msg/String
```

### Comparación con herramientas web

| Necesidad | Web | ROS 2 CLI |
|-----------|-----|-----------|
| Listar endpoints | `curl localhost/docs` | `ros2 topic list` |
| Hacer un request | `curl -X POST /endpoint` | `ros2 topic pub /topic tipo 'msg'` |
| Escuchar respuestas | `wscat -c ws://...` | `ros2 topic echo /topic` |
| Ver schema del mensaje | Swagger / OpenAPI | `ros2 interface show std_msgs/msg/String` |
| Monitor de tráfico | DevTools Network tab | `ros2 topic hz /topic` + `ros2 topic bw /topic` |
| Listar servicios activos | — | `ros2 service list` |
| Llamar un servicio | `curl -X POST` | `ros2 service call /srv tipo 'args'` |

---

## Herramientas gráficas

### rqt — Suite de plugins Qt

Suite de plugins gráficos para inspeccionar ROS 2 visualmente. Es como tener DevTools pero para ROS:

```bash
# Abrir rqt (seleccionar plugins desde el menú)
rqt

# Plugins más útiles:
rqt_topic       # Ver topics, publicar mensajes, monitorear — el más parecido a Postman
rqt_graph       # Grafo visual de nodos y topics — ver quién habla con quién
rqt_console     # Logs de todos los nodos en un solo lugar
rqt_service     # Llamar services con GUI (como el botón "Send" de Postman)
```

### Foxglove Studio — El más moderno

App de escritorio (o web) para visualizar y debugear ROS 2. Se conecta directamente a rosbridge por WebSocket — **no necesita ROS instalado**:

```
Foxglove Studio ──WSS──► rosbridge (:9090)
```

| Feature | Descripción |
|---------|-------------|
| **Panel de topics** | Ver mensajes en tiempo real, filtrar, buscar |
| **Publicar mensajes** | Editor JSON para publicar a cualquier topic |
| **Gráficos** | Plotear datos numéricos en tiempo real |
| **Logs** | Consola de logs centralizada |
| **3D** | Visualización de URDF, tf2, pointclouds |
| **Layouts** | Guardar configuraciones de panels (como collections en Postman) |

```bash
# Instalar
snap install foxglove-studio

# Conectar: Open connection → Rosbridge → ws://localhost:9090
```

---

## Aplicación al proyecto Labs Remoto

Dado que la API y las Pis se conectan por WebSocket a rosbridge, hay tres enfoques para debugear:

### Opción 1: CLI dentro del contenedor RosBridge

El contenedor de RosBridge ya tiene ROS 2 instalado. Es la forma más directa:

```bash
# Entrar al contenedor
docker exec -it rosbridge-rosbridge-1 bash

# Dentro del contenedor
source /opt/ros/humble/setup.bash

ros2 topic list                              # ¿Qué topics existen?
ros2 topic echo /robot/rabc123/command       # ¿Qué comandos llegan?
ros2 topic pub /robot/rabc123/response std_msgs/String '{"data": "test"}'  # Simular respuesta
```

### Opción 2: Foxglove Studio (sin ROS instalado)

Foxglove se conecta a rosbridge, que ya está corriendo y con el puerto 9090 expuesto en el `compose.yaml`:

```
Tu máquina (Foxglove) ──ws://localhost:9090──► contenedor RosBridge
```

No necesitás ROS instalado. Conectás al puerto 9090 y tenés una GUI completa para ver topics, publicar mensajes y monitorear en tiempo real. Bueno para demos también.

### Opción 3: Cualquier cliente WebSocket

Como rosbridge habla WebSocket/JSON, se pueden usar herramientas web directamente. Esto es literalmente lo que hacen la API y la RaspberryPi — se puede simular cualquiera de las dos desde la terminal:

```bash
# Con websocat (o wscat)
websocat ws://localhost:9090

# Suscribirte a un topic (escribir este JSON en el WS):
{"op": "subscribe", "topic": "/robot/rabc123/command", "type": "std_msgs/String"}

# Publicar un mensaje:
{"op": "publish", "topic": "/robot/rabc123/command", "msg": {"data": "{\"jsonrpc\":\"2.0\",\"method\":\"ping\",\"id\":1}"}}
```

---

## Resumen: qué usar cuándo

| Situación | Herramienta | Por qué |
|-----------|-------------|---------|
| **Quick check** — ¿llegan mensajes? | `docker exec` + `ros2 topic echo` | Rápido, ya disponible en el contenedor |
| **Debugear flujo completo** | Foxglove Studio → `ws://localhost:9090` | GUI, no necesita ROS, ve todo en tiempo real |
| **Simular una Pi o la API** | `wscat`/`websocat` → `ws://localhost:9090` | Usa el mismo protocolo que el código del proyecto |
| **Ver arquitectura** (quién publica qué) | `ros2 node info` / `rqt_graph` | Mapa visual de conexiones |
| **Tests automatizados** | `ros2 topic pub` en scripts | Reproducible, integrable en CI |

Para el día a día del proyecto: **Opción 1** (CLI dentro del contenedor) para cosas rápidas, **Opción 3** (wscat/websocat) para simular la API o una Pi. Foxglove para cuando se necesita una vista más completa o para demos.
