# CLAUDE.md — RaspberryPi

## Descripción General

Controlador que se ejecuta en cada Raspberry Pi conectada a un robot. Se comunica con la API central (FastAPI) para registrarse, autenticarse y recibir comandos, y con el Arduino vía puerto serial para controlar el brazo robótico.

## Ejecución

```bash
uv run python -m controller
# Requiere .env o .env.defaults con las variables de entorno
```

## Estructura del Código

```
controller/
├── __main__.py              # Entry point (python -m controller)
├── main.py                  # Flujo principal: config → registro → conexión → comandos
├── config.py                # Carga de variables de entorno (.env.defaults + .env)
├── server/
│   ├── __init__.py
│   └── server_service.py    # ServerServices — registro, handshake, retry, comunicación con API
└── robot/
    ├── __init__.py           # Exporta RobotController (real o mock según MOCK_ROBOT)
    ├── robot_controller.py   # Controlador real — comunicación serial con Arduino
    └── robot_mock_controller.py  # Controlador mock — simula respuestas sin hardware
```

## Variables de Entorno

Definidas en `.env.defaults` (valores por defecto), sobreescritas por `.env`:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `SERVER_URL` | URL base de la API M2M | `http://localhost:8000/m2m/robot/` |
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
   - 200 → recibe JWT, crea sesión HTTP con bearer token
   - Otro error → log warning + retry con backoff
3. Un admin debe aprobar el robot vía `POST /admin/robot/{id}/approve` para que el handshake retorne 200

### 3. Operación
1. Entra al context manager del robot (abre puerto serial o mock)
2. `get_commands()` — recibe comandos del servidor y los envía al robot

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
- **requests** — HTTP client para comunicación con la API
- **serial** / **types-pyserial** — comunicación serial con Arduino

## Modo Demo

Con `MOCK_ROBOT=1`, el controlador usa `robot_mock_controller.py` que simula el comportamiento del robot sin necesidad de hardware físico (Arduino/brazo robótico). Combinado con `CREATE_DEFAUL_METADATA=1`, permite ejecutar el flujo completo sin hardware.
