# Diseño: video de cámara USB en el WebClient

- **Fecha**: 2026-08-20
- **Servicios**: `services/PiRobotDriver/`, `services/PiSystemAgent/`, `services/Api/`, `services/WebClient/`
- **Estado**: aprobado, pendiente de plan de implementación

## Problema

El equipo de electrónica agregó `services/PiRobotDriver/agent/camera/camera_node.py`: un nodo
ROS 2 que captura frames de una cámara USB y los publica como `sensor_msgs/Image` en
`usb_cam/image_raw`. Hoy el único consumidor de ese topic es InOrbit
(`inorbit_configs/cameraDefinition.yaml`, `rosTopic: usb_cam/image_raw`, `outputEncoding: bgr8`).

El objetivo es que el video también llegue en vivo al **WebClient** (la SPA propia del proyecto)
para que el usuario final vea la cámara mientras teleopera el brazo. El pipe usuario↔robot
existente (`MicroCore` en `PiSystemAgent`, `UsersXRobotMapType` en la Api) está diseñado como
enrutador de JSON-RPC 2.0 de baja frecuencia (comandos + telemetría cada 5s) — no está pensado
para binario de video a ~30fps, y forzarlo ahí violaría la garantía de que el core "no transforma
datos" y de que cada `Strategy` habla JSON-RPC.

Bug encontrado de paso: `camera_node.py` convierte el frame a RGB
(`cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)`) y publica con `msg.encoding = 'rgb8'`, pero
`cameraDefinition.yaml` declara `outputEncoding: bgr8` para ese mismo topic — el feed de InOrbit
sale con los canales rojo/azul invertidos. Se corrige como parte de este trabajo (ver Decisión 1).

## Objetivo

Llevar el video de la cámara USB, en vivo (teleoperación, no snapshot periódico), desde la Pi
hasta el `<canvas>` del WebClient, sin tocar el pipe JSON-RPC existente ni romper el consumo
actual de InOrbit.

## Fuera de alcance

- WebRTC u otro códec de video real. JPEG por frame sobre WebSocket alcanza para LAN/intranet
  controlada; se reconsidera solo si la latencia medida resulta insuficiente.
- Multiplexar video en la conexión `/m2m/robot/connect` existente. Exigiría que `MicroCore`,
  `Strategy` y `handle_json_rpc` toleren bytes opacos además de JSON-RPC — contamina una
  abstracción hoy limpia a cambio de ahorrarse una segunda conexión WS.
- Control de vuelta desde el WebClient (pedir resolución/fps, pausar el stream, etc.). El canal
  es push-only, sin negociación.
- Buffering o cola de frames. Es "último frame gana": si el consumidor va lento, se pisa/descarta,
  nunca se acumula.
- Grabación o persistencia del video.
- Tests automatizados de extremo a extremo del `<canvas>` en el WebClient — se verifica a mano.

## Decisiones tomadas

### 1. Fix de `camera_node.py`: publicar `bgr8` nativo

Sacar el `cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)` y publicar el frame tal como lo entrega
`cv2.VideoCapture` (que ya es BGR), con `msg.encoding = 'bgr8'`. Esto arregla el mismatch con
InOrbit y de paso simplifica el nodo (una conversión menos). El topic (`usb_cam/image_raw`) no
cambia — InOrbit sigue funcionando sin tocar `cameraDefinition.yaml`.

### 2. Canal de video separado, en paralelo al `MicroCore`

Arquitectura elegida (descartando multiplexar en la conexión existente y WebRTC — ver "Fuera de
alcance"):

```
[camera_node.py] --DDS(usb_cam/image_raw, bgr8)--> [CameraRelay en PiSystemAgent]
                                                          │ WS binario dedicado
                                                          ▼
                                              [Api: WS /m2m/robot/video]
                                                          │ relay 1:1, último frame gana
                                                          ▼
                                              [Api: WS /user/robot/video]
                                                          │ WS binario
                                                          ▼
                                                    [WebClient: <canvas>]
```

No se toca `core.py`, ningún `Strategy`, ni `handle_json_rpc`. El único punto de contacto con la
infraestructura existente es reutilizar la autenticación JWT ya vigente (robot y usuario) y el
mismo proxy.

### 3. `controller/camera/camera_relay.py` (nuevo, `PiSystemAgent`)

Análogo a `Ros2Controller`/`Ros2Strategy`, pero para video:

- Nodo rclpy propio, se suscribe a `usb_cam/image_raw` (mismo topic que ya consume InOrbit).
- En el callback (thread de spin) codifica cada frame a JPEG con `cv2.imencode` y lo entrega a
  una cola asyncio vía `call_soon_threadsafe`, mismo patrón que usa `Ros2Controller._on_data`
  para telemetría, pero por-frame en vez de snapshot acumulado.
- Import diferido de `rclpy`/`cv2`, mismo patrón que `Ros2Controller`: si el entorno ROS 2 no
  está sourceado, loguea y no arranca — no rompe modo demo ni el resto del controller.
- No es un `Strategy`: es push-only, no habla JSON-RPC, no encaja en esa interfaz. Corre como
  task independiente que `main.py` arranca junto al `MicroCore`.
- Es independiente del `LOCAL_STRATEGY` activo para el brazo (`SerialStrategy`/`MockStrategy`/
  `Ros2Strategy`) — el robot puede controlarse por serial directo y aun así tener cámara vía
  ROS 2, son preocupaciones separadas.
- Abre su propio WS hacia `Api: /m2m/robot/video`, autentica con el mismo JWT robot que ya usa
  `WsStrategy`, reconecta con el mismo backoff 1s→30s.

### 4. Api: `WS /m2m/robot/video` y `WS /user/robot/video`

- `/m2m/robot/video` (`routes/m2m.py`): autentica igual que `/connect` (JWT robot). En vez de
  alimentar `ProxyStreamSource`/el pipe JSON-RPC, guarda el último frame en un `VideoRelay` nuevo
  — un objeto por robot, mismo ciclo de vida que `RobotConnection` pero sin cola (se pisa el
  frame anterior si nadie lo consumió).
- `/user/robot/video` (`routes/user.py`): valida el mismo JWT `robot_access` que ya exige
  `/user/robot/send_command` — mismo control de acceso, si el usuario no tiene sesión activa con
  ese robot no ve el video. Reenvía cada frame nuevo del `VideoRelay` tal cual, binario.
- Sigue la relación 1:1 usuario↔robot ya vigente en el resto del sistema — no hace falta pub/sub
  con múltiples viewers.

### 5. WebClient

Nuevo componente Vue que abre el WS de video, recibe frames binarios (`Blob`), los decodifica con
`createImageBitmap` y los pinta en un `<canvas>`, descartando el frame en curso si todavía se
está pintando el anterior (mismo criterio "último frame gana" que el resto del canal).

## Manejo de errores

- **Cámara no disponible / nodo ROS 2 caído**: `camera_relay.py` no recibe frames → no envía nada
  → el WebClient no muestra nada. Un placeholder "sin señal" es decisión de frontend, no
  bloqueante para este diseño.
- **`rclpy` no importable** (controller corriendo fuera del contenedor ROS 2): mismo patrón que
  `Ros2Controller` — loguea y no arranca el relay, el resto del controller sigue funcionando
  normal.
- **WS Pi↔Api se cae**: reconexión con backoff 1s→30s, igual que `WsStrategy`.
- **WS Api↔Browser se cae**: reconexión simple del lado frontend, sin backoff sofisticado (es
  solo video, no hay sesión que preservar más allá de reabrir el socket).
- **Usuario sin acceso al robot**: mismo `access_validator` que ya usa el pipe de comandos —
  403/cierre de conexión.

## Verificación

- `camera_relay.py`: mockear `rclpy`/`cv2` igual que `test_ros2.py` mockea `rclpy` para
  `Ros2Controller` — test de que un frame de entrada produce un frame JPEG en la cola de salida.
- Api: test del `VideoRelay` (frame in → frame out; robot sin viewer no rompe nada).
- Modo demo / manual: con `MOCK_ROBOT=1` no hay cámara real, así que el flujo de video requiere
  el contenedor ROS 2 con la cámara conectada (igual que `Ros2Strategy` hoy) — verificar a mano
  levantando `camera_node.py` + `camera_relay.py` + Api + WebClient y confirmando que el
  `<canvas>` muestra el video en vivo, con colores correctos (post fix de la Decisión 1).
- WebClient: verificación manual del `<canvas>` — fuera de alcance de tests automatizados (ver
  "Fuera de alcance").
