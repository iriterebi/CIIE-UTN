# CLAUDE.md — Api

## Descripción General

Monolito modular en FastAPI (Python 3.13.7+). Cumple dos roles:

1. **Punto de entrada para usuarios** — autenticación, gestión de sesiones, envío de comandos a robots vía WebSocket
2. **Punto de entrada para robots** — registro, handshake M2M y conexión WebSocket directa para comunicación bidireccional

## Ejecución

```bash
make up_dev
# equivale a: fastapi dev src/server.py
```

Requiere las variables de entorno definidas en `src/config.py` (ver sección Variables de Entorno).

## Estructura del Código

```
src/
├── server.py                          # Punto de entrada. Monta los 4 routers, lifespan conecta RosBridgeClient
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
│   ├── entities/                      # Modelos de dominio, DTOs, excepciones, constantes
│   │   ├── robot.py                   # Robot SQLModel (tabla: robots) + DTOs + RobotStatus enum + RobotStreamAutentication
│   │   ├── json_rpc_commands.py       # Modelos: RRobotCommand, RobotCommand, RobotResponse, UserWsAuthentication
│   │   └── errors.py                 # Excepciones serializables + códigos de error JSON-RPC
│   ├── adapters/                      # Implementaciones concretas de StreamSource (ver Arquitectura de Comunicación)
│   │   ├── user_stream_source.py      # UserStreamSource — adapta WS del usuario a StreamSource (valida payload)
│   │   └── robot_stream_source.py     # RobotScopedStreamSource (rosbridge), RobotWsStreamSource (WS directo), ProxyStreamSource (callback-based)
│   ├── services/                      # Lógica de negocio (clases con estado/dependencias inyectadas)
│   │   ├── robot_service.py           # RobotService — CRUD, registro, aprobación/rechazo, get_robot_by_token
│   │   ├── rosbridge_client.py        # RosBridgeClient — WS persistente a rosbridge, pub/sub de topics ROS (en deprecación)
│   │   ├── handshake_service.py       # HTTP Basic → JWT con role=robot y scopes + get_robot_by_token
│   │   ├── access_validator.py        # Valida token robot_access contra robot_id y sesión de usuario
│   │   └── ipc_user_robot_comunication.py  # UserToRobotComunication — orquestador de la conexión usuario↔robot
│   ├── repositories/                  # Acceso a datos (queries, persistencia, transacciones)
│   │   ├── robot.py                   # RobotRepository — CRUD de robots en DB
│   │   └── robot_connection.py        # RobotConnectionRepository — registro y gestión de conexiones activas (StreamConnection, pipes)
│   ├── routes/                        # Endpoints HTTP/WS (routers FastAPI)
│   │   ├── admin.py                   # /admin/robot — CRUD + aprobación/rechazo + send_command
│   │   ├── m2m.py                     # /m2m/robot — registro, handshake y conexión WS del robot
│   │   └── user.py                    # /user/robot — WebSocket para usuarios
│   └── utils/                         # Funciones stateless auxiliares
│       └── crockford_base32.py        # UUID → Crockford Base32 (para nombres de topics ROS)
│
└── user_management/                   # Módulo vacío (placeholder)
```

## Estructura Estándar de Módulos

Cada módulo del monolito debe seguir esta estructura por capas para mantener legibilidad y consistencia:

```
modulo/
├── entities/        # Modelos de dominio (SQLModel), DTOs (Pydantic), excepciones, enums, constantes
├── services/        # Lógica de negocio — clases con estado y dependencias inyectadas vía Depends
├── repositories/    # Acceso a datos — queries, persistencia, transacciones (delega al ORM)
├── routes/          # Endpoints HTTP/WS — routers FastAPI, sin lógica de negocio
└── utils/           # Funciones puras, stateless, sin dependencias inyectadas
```

**Criterios de clasificación:**
- **entities**: no tiene dependencias de otros módulos internos (excepto tipos base). Define *qué* es algo
- **services**: tiene dependencias inyectadas (`*Dep`), encapsula lógica de negocio. Define *qué hacer* con algo
- **repositories**: tiene `DbSessionDep`, encapsula acceso a datos. Define *cómo persistir* algo
- **routes**: solo orquesta — recibe request, delega a servicios, retorna response
- **utils**: funciones puras sin estado ni inyección. Si necesita `Depends`, es un servicio

## Mapa de Rutas

| Prefijo | Tag | Auth | Endpoints |
|---------|-----|------|-----------|
| `/auth` | publicas | Público (excepto /me) | `POST /login`, `POST /signup`, `GET /me`, `POST /request_robot_access` |
| `/admin/robot` | robots, admin | **Ninguna (WIP)** | `GET /list`, `GET /pending`, `GET /{robot_id}`, `POST /create`, `POST /{id}/approve`, `POST /{id}/reject`, `POST /send_command` |
| `/m2m/robot` | robots, m2m | Sin auth (interno) / HTTP Basic → JWT | `POST /register`, `POST /handshake` |
| `/user/robot` | robots, user | JWT (en mensaje WS) | `WS /send_command` |

## Flujos Principales

### Auth: Login
1. `POST /auth/login` (OAuth2PasswordRequestForm)
2. UserService busca usuario por usr_name, verifica bcrypt
3. Genera JWT con `sub=usr_name`, `role=admin|user`

### Auth: Solicitar Acceso a Robot
1. `POST /auth/request_robot_access` (requiere bearer token + robot_id en body)
2. Genera un JWT especial con `type=robot_access`, `robot_id`, `sub=usr_name`

### M2M: Registro + Aprobación del Robot
1. **Registro** (self-registration): `POST /m2m/robot/register` — robot envía `{external_identifier, psw}` (sin auth, endpoint interno protegido por proxy)
   - Si `external_identifier` no existe → crea robot con `status=pending_approval`, `name=null`
   - Si ya existe → retorna el robot existente (idempotente, noop)
2. **Handshake**: `POST /m2m/robot/handshake` — robot envía HTTP Basic (external_identifier, password)
   - HandshakeService valida credenciales
   - Si `status != approved` → 403 ("Robot no aprobado")
   - Si aprobado → genera JWT con `role=robot`, scopes
3. **Aprobación admin**: `POST /admin/robot/{id}/approve` con `{name, description}` → cambia status a `approved`
4. **Rechazo admin**: `POST /admin/robot/{id}/reject` → cambia status a `rejected`
5. **Comunicación**: tras handshake, el robot se comunica vía ROS/DDS. La API publica/suscribe topics ROS a través de RosBridge.

**Flujo desde la Pi**: registro → retry handshake con backoff exponencial (5s → 10s → 20s... hasta 300s max) → comunicación vía ROS

### User: Enviar Comando
1. Usuario conecta a `WS /user/robot/send_command`
2. Tiene 10s para enviar `UserWsAuthentication` (token)
3. AccessValidator crea sesión, valida token tipo robot_access
4. Loop: recibe comandos JSON-RPC → valida que el robot existe → valida acceso → publica al topic ROS vía RosBridgeClient
5. RosBridgeClient rutea respuestas del robot de vuelta al usuario vía `asyncio.Queue`

### Comunicación vía RosBridge
- `RosBridgeClient` (singleton) mantiene una conexión WS persistente a rosbridge (`ws://rosbridge:9090`)
- Publica comandos a `/robot/r<base32>/command` (UUIDs codificados en Crockford Base32 con prefijo `r`)
- Se suscribe lazy a `/robot/r<base32>/response` y `/robot/r<base32>/status`
- Fan-out de respuestas: cada usuario tiene su propia `asyncio.Queue`, el listener rutea mensajes por robot_id
- Reconexión automática con backoff exponencial si se pierde la conexión

## Variables de Entorno

| Variable | Uso |
|----------|-----|
| `POSTGRES_PASSWORD` | Password de PostgreSQL |
| `POSTGRES_USER` | Usuario de PostgreSQL |
| `POSTGRES_DB` | Nombre de la base de datos |
| `POSTGRES_URL` | Host de PostgreSQL (sin protocolo, ej: `localhost:5432`) |
| `ROSBRIDGE_URL` | URL WebSocket de rosbridge (ej: `ws://rosbridge:9090`) |
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
- `name` (nullable — se asigna al aprobar), `description`, `psw` (bcrypt hash)
- `status` (CHECK: `pending_approval`, `approved`, `rejected`, `disabled`), `user_id` (FK → usuarios)

## Dependencias

- **fastapi[standard]** — framework + uvicorn + websockets
- **sqlmodel** — ORM (SQLAlchemy + Pydantic)
- **psycopg2-binary** — driver PostgreSQL
- **pyjwt** — JWT encode/decode
- **bcrypt** — hashing de contraseñas
- **email-validator** — validación de EmailStr
- **passlib** — instalado pero no usado actualmente

## Patrones y Convenciones

- **Inyección de dependencias**: todo servicio se inyecta vía `Annotated[T, Depends(T)]` con su correspondiente type alias `TDep`
- **Modelos**: SQLModel para tablas (ORM + validación), Pydantic BaseModel para DTOs (Input/Output)
- **Errores**: `SerializableException` base con `to_dict()` → serialización JSON-RPC
- **JSON-RPC 2.0**: protocolo para comandos a robots (códigos de error: -32700 a -32603)
- **Naming**: campos de DB en español (`nombrecompleto`, `statuss`, `usr_name`), código en inglés
- **Roles**: `'profe'` = admin, `'alumno'` = usuario regular. En tokens se mapean a `admin`/`user`
