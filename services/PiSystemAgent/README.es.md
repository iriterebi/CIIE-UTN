# RaspberryPi

> [Read in English](./README.md)

Controlador que se ejecuta en cada Raspberry Pi conectada a un robot. Se registra y autentica con la API central (FastAPI), luego abre un WebSocket directo a la API para recibir comandos JSON-RPC 2.0 y publicar respuestas/estado. Controla el Arduino vía puerto serial.

## Índice

- [Arquitectura](#arquitectura)
- [Prerrequisitos](#prerrequisitos)
- [Ejecución](#ejecución)
- [Variables de Entorno](#variables-de-entorno)
- [Flujo Principal](#flujo-principal)
- [Modo Demo](#modo-demo)

## Arquitectura

```
                 API (FastAPI)                                        Arduino
                      ▲                                                  ▲
                      │ HTTP (registro/handshake) + WS (comandos)        │ Serial
                      │                                                  │
┌─────────────────────┴──────────────────────────────────────────────────┴─┐
│                            RaspberryPi (controller)                      │
│  server/ ──registro+handshake──►  strategy/remote/ ──comandos──► robot/  │
│                                   (ws_strategy)                          │
└──────────────────────────────────────────────────────────────────────────┘
```

1. **Registro y handshake** (HTTP): la Pi se registra en la API y obtiene un JWT
2. **Comandos** (WebSocket directo a la API): la Pi conecta a `/m2m/robot/connect` e intercambia mensajes JSON-RPC 2.0
3. **Control del robot** (Serial): traduce comandos JSON-RPC 2.0 a instrucciones seriales para el Arduino

## Prerrequisitos

- Python 3.13.7+
- Gestor de paquetes uv
- Acceso a la API (local o vía red Docker)

## Ejecución

```bash
uv run python -m controller
```

Requiere `.env` o `.env.defaults` con las variables de entorno.

## Variables de Entorno

Definidas en `.env.defaults` (valores por defecto), sobreescritas por `.env`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SERVER_URL` | URL base de la API M2M | `http://localhost:8000/m2m/robot/` |
| `ARDUINO_PORT` | Puerto serial del Arduino | (ruta USB específica) |
| `CREATE_DEFAULT_METADATA` | `1` para auto-generar credenciales al arrancar | `1` |
| `MOCK_ROBOT` | `1` para usar controlador mock sin hardware | `1` |

## Flujo Principal

### 1. Inicialización

1. Carga variables de entorno (`config.py`)
2. Crea instancia de `ServerServices`
3. Intenta cargar `robot-metadata.json` — si no existe y `CREATE_DEFAULT_METADATA=1`, genera credenciales nuevas (UUID + password aleatorio de 24 chars)

### 2. Registro y conexión (self-registration con aprobación)

1. `register()` — `POST /m2m/robot/register` con `{external_identifier, psw}` (idempotente)
2. `connect_with_retry()` — reintenta `POST /m2m/robot/handshake` (HTTP Basic) con backoff exponencial:
   - 403 → robot pendiente de aprobación, espera y reintenta (5s → 10s → 20s... hasta 300s max)
   - 200 → handshake exitoso, retorna JWT
   - Otro error → log warning + retry con backoff
3. Un admin debe aprobar el robot vía `POST /admin/robot/{id}/approve` para que el handshake retorne 200

### 3. Operación (async, WS directo a la API)

1. Entra al context manager del robot (abre puerto serial o mock)
2. `WsStrategy` abre un WebSocket a `/m2m/robot/connect` y se autentica con el JWT
3. Recibe comandos JSON-RPC 2.0 del WS, los ejecuta en el robot (serial I/O vía `run_in_executor`)
4. Envía respuestas y status periódico (cada 5s) por el mismo WS

Reconexión automática con backoff exponencial (1s → 30s) si se pierde la conexión.

## Modo Demo

Con `MOCK_ROBOT=1`, el controlador usa `robot_mock_controller.py` que simula el comportamiento del robot sin necesidad de hardware físico (Arduino/brazo robótico). Combinado con `CREATE_DEFAULT_METADATA=1`, permite ejecutar el flujo completo sin hardware.

## Despliegue (Raspberry Pi)

Se empaqueta como imagen Docker self-contained (ROS 2 Jazzy → Python 3.12) y corre vía Docker
Compose (`restart: unless-stopped`, sin systemd). Se construye con Podman en la máquina de dev
y se envía por SSH: `make deploy` (con overrides `PI_HOST`/`PI_DIR`). El controller en marcha se
gestiona con `./robot-cli <comando>` (corre la CLI dentro del contenedor vía `docker exec`).

El `Dockerfile` es multi-stage: el stage `final` (el que se sube a la Pi) hornea defaults
sensatos de `Ros2Strategy`, así que el contenedor arranca standalone sin bind-mount de código y
con solo `SERVER_URL`/`ARDUINO_PORT` pasados en runtime — el resto de la config ya tiene defaults
que funcionan.

En una Pi que todavía no tiene `.env` (es decir, su primer deploy), copiar `.env.deploy.example`
a `.env` en la Pi y ajustar `SERVER_URL` antes de correr `make deploy.up` (o el `make deploy`
encadenado, que falla en ese paso sin él) — `compose.yaml` requiere que `.env` exista. Los
redeploys siguientes pueden usar `make deploy` sin más.

Diseño: [`docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`](../../docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md).
Ver versión en inglés: [README.md](README.md).
