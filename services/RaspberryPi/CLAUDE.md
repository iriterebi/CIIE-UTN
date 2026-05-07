# CLAUDE.md — RaspberryPi

## Descripción General

Controlador que se ejecuta en cada Raspberry Pi conectada a un robot. Se registra y autentica con la API central (FastAPI), luego abre un WebSocket directo a la API (endpoint `/m2m/robot/connect`) para recibir comandos JSON-RPC 2.0 y publicar respuestas/estado. Controla el Arduino vía puerto serial.

**Arquitectura interna**: micro core asyncio + strategies intercambiables (local/remoto) + Unix socket para gestión vía CLI. Ver `ARQUITECTURA.md`.

## Ejecución

```bash
uv run python -m controller
# Requiere .env o .env.defaults con las variables de entorno
```

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
│   │   └── mock_strategy.py      # Wrappea RobotMockController (sin hardware)
│   └── remote/
│       └── ws_strategy.py        # WS directo a /m2m/robot/connect (JSON-RPC 2.0)
├── server/
│   └── server_service.py    # ServerServices — registro y handshake HTTP con la API
└── robot/
    ├── __init__.py          # Exporta RobotController (real o mock según MOCK_ROBOT)
    ├── robot_controller.py  # Comunicación serial con Arduino
    └── robot_mock_controller.py  # Mock sin hardware
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
| `LOCAL_STRATEGY` | Strategy local al arrancar | `MockStrategy` |
| `REMOTE_STRATEGY` | Strategy remoto al arrancar | `WsStrategy` |
| `SOCKET_PATH` | Ruta del Unix socket de gestión | `/tmp/robot-controller.sock` |

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
