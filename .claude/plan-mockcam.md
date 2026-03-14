# Plan provisional: MockCam — Servicio de stream MJPEG con telemetría

## Concepto

Servicio independiente que se suscribe a los topics de status de los robots vía rosbridge, genera imágenes 2D del brazo articulado con Pillow usando los ángulos de los servos, y las sirve como stream MJPEG por HTTP. Funciona como mock de una futura cámara real conectada a la Pi.

## Posición en la arquitectura

```
                                          ┌──────────────────────┐
                                          │   Frontend (Vue)     │
                                          │  <img src="/stream"> │
                                          └──────────┬───────────┘
                                                     │ HTTP GET
                                                     ▼
┌─────────────┐    status.update     ┌───────────────────────────┐
│  RosBridge   │ ──── WS/ROS ──────→ │  MockCam (servicio nuevo) │
│  (existente) │                     │  - suscribe a /status     │
└─────────────┘                      │  - genera imagen Pillow   │
       ▲                             │  - sirve MJPEG stream     │
       │ publica status              └───────────────────────────┘
┌──────┴──────┐                         puerto 8081
│ RaspberryPi │
│ (existente) │
└─────────────┘
```

MockCam NO pasa por la API. Se conecta directamente a rosbridge como suscriptor. Esto es correcto porque la cámara real tampoco pasaría por la API.

## Stack

- Python 3.13 (consistente con el resto)
- Pillow para generar imágenes
- FastAPI (o servidor HTTP mínimo — solo un endpoint de streaming)
- websockets (librería) para conectarse a rosbridge

Sin base de datos, sin auth, sin estado persistente.

## Estructura del subproyecto

```
MockCam/
├── src/
│   ├── server.py              # Punto de entrada, endpoint MJPEG
│   ├── config.py              # Variables de entorno
│   ├── rosbridge_listener.py  # Cliente WS suscrito a topics de status
│   ├── frame_generator.py     # Lógica de dibujo con Pillow
│   └── arm_renderer.py        # Dibujo específico del brazo articulado
├── Dockerfile
├── compose.yaml
├── Makefile                   # make up, make down, make build
├── pyproject.toml
├── README.md
└── README.es.md
```

## Flujo interno

```
1. Arranque
   └→ Lee config (ROSBRIDGE_URL, puerto, FPS)
   └→ Se conecta a rosbridge vía WebSocket

2. Recepción de telemetría (cada ~5s, según intervalo de la Pi)
   └→ Recibe JSON-RPC notification: {"method": "status.update", "params": {"servos": {...}}}
   └→ Actualiza estado interno del robot (último status conocido)

3. Request HTTP: GET /stream/{robot_id}
   └→ Content-Type: multipart/x-mixed-replace
   └→ Loop:
       - Toma último estado conocido del robot
       - Genera imagen con Pillow (brazo articulado 2D)
       - Envía frame JPEG
       - Espera 1/FPS segundos
       - Repite hasta que el cliente desconecta
```

La telemetría llega cada 5s, pero el stream puede correr a 5-10 FPS. Entre updates el frame es el mismo. No tiene sentido más FPS para un dibujo que cambia cada 5s.

## Imagen generada

Brazo articulado 2D visto de perfil. Cada segmento es una línea gruesa con color distinto. Los joints son círculos. Los ángulos reales rotan cada segmento respecto al anterior (cinemática directa 2D).

Elementos visuales:
- Labels con nombre y ángulo de cada servo
- Base/piso visual
- Nombre/ID del robot y timestamp en el fondo
- Indicador de estado (online/offline, mock/real)
- Borde rojo si el robot está desconectado

Resolución: 640x480 (configurable). Es informativo, no necesita ser bonito.

Servos del brazo (7 total, ángulos 0-180°):
1. base — rotación de todo el brazo
2. cuerpo — torso
3. hombro — articulación del hombro
4. brazo — brazo superior
5. antebrazo_1 — primer segmento del antebrazo
6. antebrazo_2 — segundo segmento
7. mano — pinza/gripper

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `ROSBRIDGE_URL` | `ws://localhost:9090` | URL del rosbridge |
| `MOCKCAM_PORT` | `8081` | Puerto HTTP del stream |
| `MOCKCAM_FPS` | `5` | Frames por segundo |
| `MOCKCAM_RESOLUTION` | `640x480` | Resolución de imagen |

## Consumo desde frontend

```html
<img src="http://mockcam:8081/stream/{robot_id}" />
```

MJPEG es nativo en `<img>`. Sin JS, sin WebSocket, sin librerías de video.

## Descubrimiento de robots: estrategia lazy

No se suscribe a nada al arrancar. Cuando llega un `GET /stream/{robot_id}`, recién ahí se suscribe al topic de ese robot. Si nadie pide el stream, no consume recursos.

## Transición a cámara real

- **Pi sirve MJPEG directo** (motion/mjpg-streamer): MockCam se convierte en proxy/router, o se reemplaza la URL en frontend.
- **Cámara publica en ROS** (sensor_msgs/CompressedImage): MockCam cambia fuente — en vez de dibujar, decodifica frames del topic ROS y los re-sirve como MJPEG. Frontend no cambia.
- MockCam podría seguir como fallback: si no hay cámara → dibuja; si hay → re-streamea.

## Docker Compose

```yaml
mockcam:
  build: ./MockCam
  ports:
    - "8081:8081"
  environment:
    - ROSBRIDGE_URL=ws://rosbridge:9090
  depends_on:
    - rosbridge
  networks:
    - ciie-test
```

## Limitaciones del servicio

- No autentica usuarios (proxy/nginx en producción)
- No almacena datos
- No envía comandos (read-only)
- No reemplaza el WebSocket de la API para telemetría textual — coexisten

## Dato importante: estado actual de la telemetría

- El mock controller ya publica ángulos de los 7 servos cada 5s
- El real controller solo reporta estado de conexión (no lee posiciones del Arduino)
- Para el real, habría que trackear los últimos ángulos enviados como comando (mejora futura en RaspberryPi)
