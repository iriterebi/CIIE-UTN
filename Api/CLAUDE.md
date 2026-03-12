# CLAUDE.md — Api

## Descripción General

Monolito modular en FastAPI (Python 3.13.7+). Cumple dos roles:

1. **Punto de entrada para usuarios** — autenticación, gestión de sesiones, envío de comandos a robots vía WebSocket
2. **Punto de entrada para robots** — handshake M2M, recepción de comandos y (futuro) reporte de estado

## Ejecución

```bash
make up_dev
# equivale a: fastapi dev src/server.py
```

Requiere las variables de entorno definidas en `src/config.py` (ver sección Variables de Entorno).

## Estructura del Código

```
src/
├── server.py                          # Punto de entrada. Monta los 4 routers en la app FastAPI
├── config.py                          # Carga y valida env vars (falla al iniciar si faltan)
│
├── db_connection/
│   └── db_connection.py               # Engine SQLModel + session dependency (DbSessionDep)
│
├── auth/                              # Módulo de autenticación
│   ├── routes.py                      # /auth — login, signup, me, request_robot_access
│   └── services/
│       ├── encryption/
│       │   ├── config.py              # EncryptionServiceConfiguration (dataclass)
│       │   ├── encryption_service.py  # JWT encode/decode, bcrypt hash/verify
│       │   └── access_token.py        # Modelo AccessToken, esquema OAuth2, TokenStrDep
│       └── user/
│           ├── user.py                # User SQLModel (tabla: usuarios)
│           ├── user_base.py           # UserBase (Pydantic, para signup)
│           ├── user_service.py        # UserService — CRUD usuarios, creación de tokens
│           └── current_user.py        # Dependencia get_current_user
│
├── robot/                             # Módulo de robots
│   ├── routes_admin.py                # /admin/robot — CRUD + send_command (sin auth actualmente)
│   ├── routes_m2m.py                  # /m2m/robot — handshake + WebSocket para robots
│   ├── routes_user.py                 # /user/robot — WebSocket para usuarios
│   ├── access_validator.py            # Valida token robot_access contra robot_id y sesión de usuario
│   ├── handshake/
│   │   └── handshake_service.py       # HTTP Basic → JWT con role=robot y scopes
│   └── robot/
│       ├── robot.py                   # Robot SQLModel (tabla: robots) + RobotInput/RobotOutput
│       ├── robot_service.py           # RobotService — CRUD robots, get_robot_by_token
│       ├── robot_connection.py        # RobotConnection — WS del robot, se suscribe al IPC subject
│       ├── ipc_user_robot_comunication.py  # UserToRobotCommunication — WS del usuario, IPC global
│       ├── json_rpc_commands.py       # Modelos: RobotCommand, RobotCommandExtended, RobotResponse, UserWsAuthentication
│       └── errors.py                  # Excepciones serializables + códigos de error JSON-RPC
│
└── user_management/                   # Módulo vacío (placeholder)
```

## Mapa de Rutas

| Prefijo | Tag | Auth | Endpoints |
|---------|-----|------|-----------|
| `/auth` | publicas | Público (excepto /me) | `POST /login`, `POST /signup`, `GET /me`, `POST /request_robot_access` |
| `/admin/robot` | robots, admin | **Ninguna (WIP)** | `GET /list`, `GET /{robot_id}`, `POST /create`, `POST /send_command` |
| `/m2m/robot` | robots, m2m | HTTP Basic → JWT | `POST /handshake`, `WS /commands/{auth_token}` |
| `/user/robot` | robots, user | JWT (en mensaje WS) | `WS /send_command` |

## Flujos Principales

### Auth: Login
1. `POST /auth/login` (OAuth2PasswordRequestForm)
2. UserService busca usuario por usr_name, verifica bcrypt
3. Genera JWT con `sub=usr_name`, `role=admin|user`

### Auth: Solicitar Acceso a Robot
1. `POST /auth/request_robot_access` (requiere bearer token + robot_id en body)
2. Genera un JWT especial con `type=robot_access`, `robot_id`, `sub=usr_name`

### M2M: Handshake + Conexión del Robot
1. `POST /m2m/robot/handshake` — robot envía HTTP Basic (external_identifier, password)
2. HandshakeService valida credenciales → genera JWT con `role=robot`, scopes
3. Robot conecta a `WS /m2m/robot/commands/{token}`
4. RobotConnection acepta WS, se suscribe al AsyncSubject (IPC) filtrando por robot.id
5. Loop: recibe respuestas del robot → las emite al subject

### User: Enviar Comando
1. Usuario conecta a `WS /user/robot/send_command`
2. Tiene 10s para enviar `UserWsAuthentication` (token)
3. AccessValidator crea sesión, valida token tipo robot_access
4. Loop: recibe comandos JSON-RPC → valida que el robot existe → valida acceso → publica al IPC subject
5. RobotConnection recibe el comando y lo envía al robot por su WS

### IPC (Comunicación Inter-Procesos)
- Singleton global `AsyncSubject` (aioreactive) actúa como bus de mensajes
- Los comandos del usuario se publican al subject
- RobotConnection se suscribe filtrando por `robot_id`
- Las respuestas del robot se emiten de vuelta al mismo subject

## Variables de Entorno

| Variable | Uso |
|----------|-----|
| `POSTGRES_PASSWORD` | Password de PostgreSQL |
| `POSTGRES_USER` | Usuario de PostgreSQL |
| `POSTGRES_DB` | Nombre de la base de datos |
| `POSTGRES_URL` | Host de PostgreSQL (sin protocolo, ej: `localhost:5432`) |
| `JWT_SECRET_KEY` | Secret para firmar JWTs |
| `JWT_ALGORITHM` | Algoritmo JWT (ej: `HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de expiración del token |

## Modelos de Base de Datos

### User (`usuarios`)
- `id` (int, PK auto), `nombrecompleto`, `email` (unique), `usr_name` (unique), `usr_psw` (bcrypt hash)
- `statuss` (enum: profe/alumno), `usr_pronouns`, `accion`
- Property `is_admin` → `statuss == 'profe'`

### Robot (`robots`)
- `id` (UUID, PK, gen_random_uuid()), `external_identifier` (string, unique, indexed)
- `name`, `description`, `psw` (bcrypt hash), `status`, `user_id` (FK → usuarios)

## Dependencias

- **fastapi[standard]** — framework + uvicorn
- **sqlmodel** — ORM (SQLAlchemy + Pydantic)
- **psycopg2-binary** — driver PostgreSQL
- **pyjwt** — JWT encode/decode
- **bcrypt** — hashing de contraseñas
- **aioreactive** — AsyncSubject para IPC reactivo
- **reactivex** — extensiones reactivas (usado en imports de rutas admin)
- **email-validator** — validación de EmailStr
- **passlib** — instalado pero no usado actualmente

## Patrones y Convenciones

- **Inyección de dependencias**: todo servicio se inyecta vía `Annotated[T, Depends(T)]` con su correspondiente type alias `TDep`
- **Modelos**: SQLModel para tablas (ORM + validación), Pydantic BaseModel para DTOs (Input/Output)
- **Errores**: `SerializableException` base con `to_dict()` → serialización JSON-RPC
- **JSON-RPC 2.0**: protocolo para comandos a robots (códigos de error: -32700 a -32603)
- **Naming**: campos de DB en español (`nombrecompleto`, `statuss`, `usr_name`), código en inglés
- **Roles**: `'profe'` = admin, `'alumno'` = usuario regular. En tokens se mapean a `admin`/`user`
