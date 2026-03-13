# RaspberryPi

> [Read in English](./README.md)

Controlador que se ejecuta en cada Raspberry Pi conectada a un robot. Se registra y autentica con la API central (FastAPI), luego se conecta a rosbridge vía WebSocket para recibir comandos ROS y publicar respuestas/estado. Controla el Arduino vía puerto serial.

## Índice

- [Arquitectura](#arquitectura)
- [Prerrequisitos](#prerrequisitos)
- [Ejecución](#ejecución)
- [Variables de Entorno](#variables-de-entorno)
- [Flujo Principal](#flujo-principal)
- [Modo Demo](#modo-demo)

## Arquitectura

```
API (FastAPI)                    rosbridge (:9090)                Arduino
     │                               ▲     │                        ▲
     │ HTTP (registro/handshake)     │     │ WS (subscribe)        │ Serial
     ▼                               │     ▼                        │
┌─────────────────────────────────────────────────────────────────────┐
│                         RaspberryPi                                 │
│  server/ ──registro+handshake──►   rosbridge/ ──comandos──► robot/ │
└─────────────────────────────────────────────────────────────────────┘
```

1. **Registro y handshake** (HTTP): la Pi se registra en la API y obtiene un JWT + topic base (`/robot/r<base32>`)
2. **Comandos** (WebSocket vía rosbridge): la Pi se suscribe a su topic de comandos y publica respuestas/estado
3. **Control del robot** (Serial): traduce comandos JSON-RPC 2.0 a instrucciones seriales para el Arduino

## Prerrequisitos

- Python 3.13.7+
- Gestor de paquetes uv
- Acceso a la API y a rosbridge (local o vía red Docker)

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
| `ROSBRIDGE_URL` | URL WebSocket de rosbridge | `ws://localhost:9090` |
| `ARDUINO_PORT` | Puerto serial del Arduino | (ruta USB específica) |
| `CREATE_DEFAUL_METADATA` | `1` para auto-generar credenciales al arrancar | `1` |
| `MOCK_ROBOT` | `1` para usar controlador mock sin hardware | `1` |

## Flujo Principal

### 1. Inicialización

1. Carga variables de entorno (`config.py`)
2. Crea instancia de `ServerServices`
3. Intenta cargar `robot-metadata.json` — si no existe y `CREATE_DEFAUL_METADATA=1`, genera credenciales nuevas (UUID + password aleatorio de 24 chars)

### 2. Registro y conexión (self-registration con aprobación)

1. `register()` — `POST /m2m/robot/register` con `{external_identifier, psw}` (idempotente)
2. `connect_with_retry()` — reintenta `POST /m2m/robot/handshake` (HTTP Basic) con backoff exponencial:
   - 403 → robot pendiente de aprobación, espera y reintenta (5s → 10s → 20s... hasta 300s max)
   - 200 → handshake exitoso, retorna JWT + topic base
   - Otro error → log warning + retry con backoff
3. Un admin debe aprobar el robot vía `POST /admin/robot/{id}/approve` para que el handshake retorne 200

### 3. Operación (async, vía rosbridge)

1. Entra al context manager del robot (abre puerto serial o mock)
2. `PiRosBridgeClient` conecta a rosbridge vía WebSocket
3. Se suscribe al topic `/robot/r<base32>/command` para recibir comandos JSON-RPC 2.0
4. Al recibir un comando, lo ejecuta en el robot (serial I/O vía `run_in_executor`)
5. Publica la respuesta en `/robot/r<base32>/response`
6. Publica estado periódico (cada 5s) en `/robot/r<base32>/status`

Reconexión automática con backoff exponencial (1s → 30s) si se pierde la conexión.

## Modo Demo

Con `MOCK_ROBOT=1`, el controlador usa `robot_mock_controller.py` que simula el comportamiento del robot sin necesidad de hardware físico (Arduino/brazo robótico). Combinado con `CREATE_DEFAUL_METADATA=1`, permite ejecutar el flujo completo sin hardware.
