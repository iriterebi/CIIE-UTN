# CLAUDE.md — RaspberryPi

## Descripción General

Controlador que se ejecuta en cada Raspberry Pi conectada a un robot. Se registra y autentica con la API central (FastAPI), luego abre un WebSocket directo a la API (endpoint `/m2m/robot/connect`) para recibir comandos JSON-RPC 2.0 y publicar respuestas/estado. Controla el Arduino vía puerto serial.

**Arquitectura interna**: micro core asyncio + strategies intercambiables (local/remoto) + Unix socket para gestión vía CLI. Ver `ARQUITECTURA.md`.

## Ejecución

```bash
uv run python -m controller
# Requiere .env o .env.defaults con las variables de entorno
```

Esto corre el controller con el Python gestionado por uv (3.13) y sirve para `MockStrategy` /
`SerialStrategy`. **No** sirve para `Ros2Strategy`, que necesita `rclpy` (ver abajo).

### Correr Ros2Strategy con Podman (ROS 2 Jazzy)

`rclpy`/`std_msgs` no se instalan con uv (son extensiones compiladas atadas al Python de ROS), así
que `Ros2Strategy` se corre dentro de un contenedor `ros:jazzy` (Ubuntu 24.04, Python 3.12 — el
controller corre sin cambios de código). Requiere podman instalado en el host
(`sudo apt install -y podman uidmap`). Podman es rootless: no necesita grupo ni daemon.

```bash
make ros.build     # construye la imagen (Dockerfile)
make ros.verify    # comprueba que rclpy + std_msgs importan
make ros.test      # corre pytest dentro del contenedor (rclpy real disponible)
make ros.shell     # bash interactivo con ROS sourceado (ros2 topic echo/pub)
make ros.run       # corre el controller con LOCAL_STRATEGY=Ros2Strategy
```

Los targets usan `podman run` plano con `--network=host` (discovery DDS con el agente ROS y acceso a
la API en `localhost`) y montan el código como volumen (incluido el `.env`). `rclpy` vive solo en el
contenedor; el host sigue usando uv para mock/serial.

> **Transporte DDS entre contenedores**: el agente ROS corre en otro contenedor con su propio
> `/dev/shm`, así que el transporte por memoria compartida de Fast DDS (default same-host) **no
> entrega datos** entre contenedores aunque el descubrimiento (UDP multicast) sí cruce. La imagen
> hornea `ENV FASTDDS_BUILTIN_TRANSPORTS=UDPv4` para forzar UDP y que la telemetría/los comandos
> fluyan. (Alternativa: `--ipc=host` en ambos contenedores para compartir `/dev/shm`.)
>
> **Entornos restringidos/anidados** (VM/contenedor donde podman no puede crear namespaces; error
> `mount 'proc' to 'proc': Operation not permitted`): agregar `--isolation=chroot` al `podman build`
> y `--pid=host` al `podman run`. En una máquina normal no hacen falta.

### Deploy en la Pi (Docker Compose)

El controller se empaqueta como imagen Docker self-contained (ROS 2 Jazzy → **Python 3.12**;
ver `docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`). El Python
3.11 del host Raspbian no se usa: el contenedor trae su propio intérprete.

- **Artefacto**: `services/RaspberryPi/Dockerfile` (único archivo: copia el código para el
  artefacto de deploy y, vía bind-mount de los targets `ros.*`, también sirve de imagen de
  iteración local con `rclpy` real — reemplaza al extinto `Dockerfile.ros`).
- **Runtime**: `compose.yaml` — un servicio `controller`, `network_mode: host`,
  `restart: unless-stopped`, `container_name: labs-remoto-robot`. Sin systemd: el ciclo de vida
  lo cubre la restart policy de Docker. Sin passthrough de serial (el Arduino lo maneja el agente ROS).
- **Config**: copiar `.env.deploy.example` → `.env` en la Pi y ajustar `SERVER_URL`. La identidad
  del robot persiste en `./data/` (montado).
- **Control**: `./robot-cli <comando>` corre la CLI dentro del contenedor vía `docker exec`
  (el host es 3.11, la CLI usa 3.12). En dev: `CONTAINER_ENGINE=podman ./robot-cli status`.

Build y entrega (Podman en dev — docker no está en dev — → `docker load` en la Pi):

    make deploy.build      # cross-build arm64 + save (docker-archive). Requiere binfmt qemu.
    make deploy.push       # docker load por SSH + scp de compose/robot-cli/.env.example
    make deploy.up         # docker compose up -d en la Pi
    make deploy            # los tres encadenados
    # PI_HOST y PI_DIR son overridables: make deploy PI_HOST=usuario@ip

> La Pi usa **Docker** (como sus otros contenedores ROS), no Podman/quadlets. Divergencia
> intencional respecto al servidor central. La Pi está fuera de `quadlets/deploy.sh`.

## Estructura del Código

```
controller/
├── __main__.py              # Entry point (python -m controller)
├── main.py                  # Registry + factory de strategies, arranca el core
├── config.py                # Carga de variables de entorno (.env.defaults + .env)
├── core.py                  # MicroCore: enruta entre strategies + socket de gestión
├── socket_server.py         # Unix socket JSON-RPC 2.0 (CLI ↔ core)
├── cli.py                   # CLI independiente (proceso separado)
├── type_defs.py             # TypedDicts compartidos
├── json_rpc.py              # Modelos pydantic + handler de comandos JSON-RPC 2.0
├── strategy/
│   ├── base.py              # ABC Strategy + LocalStrategy (telemetry)
│   ├── registry.py          # StrategyRegistry (lista por nombre)
│   ├── local/
│   │   ├── serial_strategy.py    # Wrappea RobotController (Arduino real)
│   │   ├── mock_strategy.py      # Wrappea RobotMockController (sin hardware)
│   │   └── ros2_strategy.py      # Wrappea Ros2Controller (IPC ROS 2 / DDS)
│   └── remote/
│       └── ws_strategy.py        # WS directo a /m2m/robot/connect (JSON-RPC 2.0)
├── server/
│   └── server_service.py    # ServerServices — registro y handshake HTTP con la API
├── tests/
│   └── test_ros2.py         # Tests del controlador/strategy ROS 2 (rclpy mockeado)
└── robot/
    ├── __init__.py          # Exporta RobotController (real o mock según MOCK_ROBOT)
    ├── robot_controller.py  # Comunicación serial con Arduino
    ├── robot_mock_controller.py  # Mock sin hardware
    └── ros2_controller.py   # Nodo rclpy: publica comandos / suscribe telemetría (import diferido)
```

## Variables de Entorno

Definidas en `.env.defaults` (valores por defecto), sobreescritas por `.env`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SERVER_URL` | URL base de la API M2M | `http://localhost:8000/m2m/robot/` |
| `ARDUINO_PORT` | Puerto serial del Arduino | (ruta USB específica) |
| `CREATE_DEFAULT_METADATA` | `1` para auto-generar credenciales al arrancar | `1` |
| `MOCK_ROBOT` | `1` para usar controlador mock sin hardware | `1` |
| `METADATA_FILE` | Ruta al archivo de credenciales | `./robot-metadata.json` |
| `LOCAL_STRATEGY` | Strategy local al arrancar (`MockStrategy`/`SerialStrategy`/`Ros2Strategy`) | `MockStrategy` |
| `REMOTE_STRATEGY` | Strategy remoto al arrancar | `WsStrategy` |
| `SOCKET_PATH` | Ruta del Unix socket de gestión | `/tmp/robot-controller.sock` |
| `ROS2_NODE_NAME` | Nombre del nodo rclpy (`Ros2Strategy`) | `labs_remoto_robot` |
| `ROS2_COMMAND_TOPIC` | Topic donde se publican los comandos (`Ros2Strategy`) | `/inorbit/custom_command` |
| `ROS2_DATA_TOPIC` | Topic de telemetría `Key=Value` que se suscribe (`Ros2Strategy`) | `/inorbit/custom_data` |
| `ROS2_DOMAIN_ID` | Dominio DDS — debe coincidir con el agente ROS de la Pi (`Ros2Strategy`) | `42` |

> **Ros2Strategy**: comunica con el robot vía ROS 2 (IPC interno de la Pi sobre DDS) en vez de serial.
> Publica los comandos como `std_msgs/String` en `ROS2_COMMAND_TOPIC` y se suscribe a `ROS2_DATA_TOPIC`
> para la telemetría (formato `Key=Value`, claves `Modo`/`Tension`/`Velocidad`). El agente ROS
> contraparte (el `serial_scraper` que habla con el Arduino) es *fire-and-forget* (no responde
> comandos), así que `read_response()` retorna un ack sintético. **Para que los nodos se descubran por
> DDS, `ROS2_DOMAIN_ID` debe coincidir con el del agente (42).** `Ros2Controller.connect()` lo fija vía
> `ROS_DOMAIN_ID` (la imagen Docker también lo hornea con `ENV ROS_DOMAIN_ID=42`). `rclpy` **no se
> instala vía uv**: viene del entorno ROS 2 sourceado, y se importa de forma diferida (no rompe el modo
> demo sin ROS 2).

## Flujo Principal

### 1. Inicialización
1. Carga variables de entorno (`config.py`)
2. `main.py` arma el `StrategyRegistry`, instancia local y remoto por nombre y los inyecta en el `MicroCore`
3. El core arranca el Unix socket (gestión vía CLI), arranca los strategies y enruta mensajes en ambas direcciones

### 2. WsStrategy: registro y conexión
1. **Registro HTTP** (`POST /m2m/robot/register`): idempotente, con `{external_identifier, psw}` cargados/generados desde `robot-metadata.json`
2. **Handshake HTTP** (`POST /m2m/robot/handshake` con HTTP Basic) — backoff exponencial:
   - 403 → robot pendiente de aprobación, espera y reintenta (5s → 10s → 20s... hasta 300s max)
   - 200 → retorna JWT
3. Un admin debe aprobar el robot vía `POST /admin/robot/{id}/approve` para que el handshake retorne 200
4. **Apertura del WS** a `/m2m/robot/connect`:
   - El servidor envía challenge `{method: "send_credentials"}`
   - La Pi responde `{token: <JWT>}`
   - El servidor confirma con `{status: "success auth"}`

### 3. Operación
1. La strategy local entra al context manager del robot (abre puerto serial o mock)
2. La `WsStrategy` lee mensajes JSON-RPC 2.0 del WS y los entrega al core
3. El core enruta los comandos a la strategy local; las respuestas y la telemetría periódica (cada 5s) vuelven al WS por el mismo camino
4. Reconexión automática con backoff exponencial (1s → 30s) si se pierde la conexión WS

## Archivo `robot-metadata.json`

Generado automáticamente o provisto manualmente. Contiene las credenciales del robot:

```json
{
    "robot_id": "550e8400-e29b-41d4-a716-446655440000",
    "robot_psw": "aB3$kL9...(24 chars)",
    "creation_time": 1710200000
}
```

- `robot_id` = `external_identifier` del robot (UUID, actúa como usuario interno)
- `robot_psw` = contraseña en texto plano (se envía al servidor, que la almacena hasheada con bcrypt)
- Este archivo NO se versiona (está en `.gitignore`)

## Dependencias

- **python-dotenv** — carga de `.env`
- **requests** — HTTP client para registro y handshake con la API
- **websockets** — cliente WebSocket para `/m2m/robot/connect`
- **pyserial** / **types-pyserial** — comunicación serial con Arduino
- **pydantic** / **pydantic-settings** — modelos JSON-RPC y carga de configuración

## Modo Demo

Con `MOCK_ROBOT=1`, el controlador usa `robot_mock_controller.py` que simula el comportamiento del robot sin necesidad de hardware físico (Arduino/brazo robótico). Combinado con `CREATE_DEFAULT_METADATA=1`, permite ejecutar el flujo completo sin hardware.
