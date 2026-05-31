# Arquitectura del Sistema — Labs Remoto

## Índice

- [Visión General](#visión-general)
- [Diagrama de Arquitectura](#diagrama-de-arquitectura)
- [Componentes](#componentes)
  - [Frontend](#frontend)
  - [API (Backend)](#api-backend)
  - [Base de Datos](#base-de-datos)
  - [ROS 2](#ros-2)
  - [RaspberryPi (Controlador del Robot)](#raspberrypi-controlador-del-robot)
  - [Arduino (Firmware)](#arduino-firmware)
- [Modelo de Datos](#modelo-de-datos)
- [Protocolos de Comunicación](#protocolos-de-comunicación)
  - [HTTP/REST](#httprest)
  - [WebSocket](#websocket)
  - [JSON-RPC 2.0](#json-rpc-20)
  - [Serial](#serial)
- [Flujos de Comunicación](#flujos-de-comunicación)
  - [Autenticación de Usuario](#autenticación-de-usuario)
  - [Conexión del Robot](#conexión-del-robot)
  - [Usuario Envía Comando a Robot](#usuario-envía-comando-a-robot)
- [Autenticación y Autorización](#autenticación-y-autorización)
- [Despliegue](#despliegue)
- [Modo Demo](#modo-demo)

---

## Visión General

Labs Remoto es un sistema distribuido que permite a usuarios (profesores y alumnos) controlar robots en laboratorios de forma remota a través de una interfaz web. La comunicación fluye desde el navegador del usuario hasta los motores del robot, pasando por múltiples capas.

El sistema sigue una arquitectura **lineal** con la API actuando como hub: cada Raspberry Pi abre un WebSocket directo y persistente contra la API, y los usuarios hablan con la API por otro WebSocket. La API enruta mensajes entre ambos lados sin pasar por un intermediario externo.

```
Usuario → Frontend ↔ API ↔ RaspberryPi → Arduino → Robot Físico
```

---

## Diagrama de Arquitectura

```
┌─────────────┐
│ WebClient   │  Frontend Vue 3 + TypeScript
│ (Vite +     │
│  PicoCSS)   │
└──────┬──────┘
       │ HTTP / WebSocket
       ▼
┌─────────────┐         ┌─────────────┐
│    API      │◄───────►│ PostgreSQL  │
│  (FastAPI)  │         │   17.5      │
│             │         └─────────────┘
│  - Auth     │
│  - Sesiones │
│  - Pipe U↔R │
└──────┬──────┘
       │ WebSocket (JSON-RPC 2.0)
       │ — un WS por robot —
       ▼
┌─────────────┐
│ RaspberryPi │  Un controlador por robot.
│ (Python)    │  Mantiene WS persistente
│             │  contra /m2m/robot/connect
└──────┬──────┘
       │ Serial (USB)
       ▼
┌─────────────┐
│  Arduino    │  Firmware: control de servos
│  (C++)      │
└─────────────┘
```
---

## Componentes

### Frontend

- **Directorio**: `services/WebClient/`
- **Tecnología**: Vue 3, TypeScript, Vite, PicoCSS, Vue Router, Pinia
- **Responsabilidad**: Interfaz de usuario para autenticación, selección de robot y envío de comandos de control
- **Comunicación con API**: HTTP para auth y CRUD, WebSocket para comandos en tiempo real
- **Despliegue**: Multi-stage Docker (node build → nginx serve), reverse proxy a API y WebSocket

### API (Backend)

- **Directorio**: `services/Api/`
- **Tecnología**: Python 3.13.7+, FastAPI, SQLModel
- **Tipo**: Monolito modular
- **Responsabilidad**: Punto central del sistema. Maneja:
  - Autenticación y autorización de usuarios (JWT + bcrypt)
  - Registro y autenticación de robots (handshake M2M)
  - Puente de comunicación usuario↔robot en tiempo real
  - Validación de acceso a robots
  - CRUD de usuarios y robots

#### Módulos internos

| Módulo | Rutas | Responsabilidad |
|--------|-------|-----------------|
| `auth` | `/auth/*` | Login, signup, token de acceso a robot |
| `robot` (admin) | `/admin/robot/*` | CRUD de robots, envío de comandos (admin) |
| `robot` (m2m) | `/m2m/robot/*` | Registro y handshake para robots |
| `robot` (user) | `/user/robot/*` | WebSocket para usuarios |

#### Comunicación usuario↔robot

La RaspberryPi mantiene un WebSocket persistente contra `WS /m2m/robot/connect`. El usuario abre otro WebSocket contra `WS /user/robot/send_command`. La API arma un pipe bidireccional (`UsersXRobotMapType`) que conecta ambos lados y enruta mensajes sin transformaciones:

```
Usuario ──WS──► API ──WS──► RaspberryPi
                 ▲             │
                 └─────────────┘
                  (respuestas del robot)
```

- Todos los mensajes usan JSON-RPC 2.0 (comandos, respuestas y notificaciones de estado)
- La `RobotConnection` persiste entre sesiones de usuario: cuando un usuario se desconecta, su `UserConnection` cae pero la conexión del robot sigue viva esperando la próxima sesión
- Adapters: `UserStreamSource` para el WS del usuario (valida payload), `ProxyStreamSource` para el WS del robot (callback-based)
- Reconexión automática con backoff exponencial (1s→30s) desde la Pi si se pierde el WS

### Base de Datos

- **Directorio**: `services/Db/`
- **Tecnología**: PostgreSQL 17.5 (Alpine)
- **Migraciones**: dbmate
- **Responsabilidad**: Persistencia de usuarios, robots y auditoría de cambios de estado

### ROS 2

- **Directorio**: `ros_tryouts/` (workspace experimental del otro equipo, no se toca)
- **Tecnología**: ROS 2 Humble
- **Responsabilidad**: Tras el desacople del rosbridge en `raspi-arqui-refactor`, ROS 2 quedó relegado a **IPC interno del robot dentro de la Raspi** (coordinación entre componentes locales como `ros2_serial_agent` cuando se integre). No es bus API↔robot
- **Estado**: En desarrollo por otro miembro del equipo

### RaspberryPi (Controlador del Robot)

- **Directorio**: `services/RaspberryPi/`
- **Tecnología**: Python 3.13.7+
- **Responsabilidad**: Se ejecuta en cada robot físico. Maneja:
  - Registro y handshake con la API (HTTP Basic → JWT)
  - WebSocket directo a `/m2m/robot/connect` para recibir comandos JSON-RPC 2.0 y publicar respuestas/estado
  - Traducción de comandos a instrucciones seriales para Arduino
  - Reconexión automática con backoff exponencial (1s→30s)
- **Mock disponible**: `RobotMockController` (activable con `MOCK_ROBOT=1`) para desarrollo sin hardware

### Arduino (Firmware)

- **Directorio**: `services/Arduino/`
- **Tecnología**: Arduino C++
- **Responsabilidad**: Control directo del hardware — 7 servomotores del brazo robótico (base, cuerpo, hombro, brazo, antebrazo×2, mano)
- **Comunicación**: Serial USB con la RaspberryPi

---

## Modelo de Datos

```
┌──────────────────┐       ┌──────────────────────┐
│    usuarios      │       │       robots         │
├──────────────────┤       ├──────────────────────┤
│ id (PK, serial)  │◄──┐   │ id (PK, UUID)        │
│ nombrecompleto   │   │   │ external_identifier  │
│ email (unique)   │   │   │ name (nullable)      │
│ usr_name (unique)│   └───┤ user_id (FK)         │
│ usr_psw (bcrypt) │       │ psw (bcrypt)         │
│ statuss (enum)   │       │ status (CHECK)       │
│ usr_pronouns     │       │ description          │
│ accion (enum)    │       └──────────┬───────────┘
└──────────────────┘                  │
                                      │ trigger: INSERT/UPDATE
                                      ▼
                           ┌──────────────────────┐
                           │ robot_status_history │
                           ├──────────────────────┤
                           │ id (PK, serial)      │
                           │ robot_id (FK)        │
                           │ user_id (FK)         │
                           │ status               │
                           │ timestamp            │
                           └──────────────────────┘
```

### ENUMs

- **user_status**: `'profe'` (admin), `'alumno'` (usuario regular)
- **user_action**: `'Girar'`, `'Pinzar'`, `'Reverencia'`

### Relaciones

- `robots.user_id` → `usuarios.id` (ON DELETE SET NULL) — usuario actualmente asignado al robot
- `robot_status_history.robot_id` → `robots.id` (ON DELETE CASCADE)
- `robot_status_history.user_id` → `usuarios.id` (ON DELETE SET NULL)

### Auditoría Automática

Un trigger en la tabla `robots` registra automáticamente cada cambio de estado en `robot_status_history` (INSERT y UPDATE).

---

## Protocolos de Comunicación

### HTTP/REST

- **Frontend → API**: Autenticación (`/auth/login`, `/auth/signup`), administración de robots (`/admin/robot/*`)
- **RaspberryPi → API**: Registro (`POST /m2m/robot/register`) y handshake (`POST /m2m/robot/handshake` con HTTP Basic)

### WebSocket

- **Frontend → API** (`/user/robot/send_command`): Canal bidireccional para envío de comandos y recepción de respuestas del robot
- **RaspberryPi → API** (`/m2m/robot/connect`): WebSocket persistente por robot. La API enruta mensajes 1:1 entre este WS y el del usuario asociado

### JSON-RPC 2.0

Protocolo usado para los comandos a robots. Incluye manejo de errores estándar:

| Código | Significado |
|--------|-------------|
| -32700 | Error de parseo |
| -32600 | Request inválido |
| -32601 | Método no encontrado |
| -32602 | Parámetros inválidos |
| -32603 | Error interno |

### Serial

- **RaspberryPi → Arduino**: Comunicación USB serial para control de servomotores

---

## Flujos de Comunicación

### Autenticación de Usuario

```
Usuario                    API                      DB
  │                         │                        │
  ├─POST /auth/login───────►│                        │
  │  (usr_name, password)   ├──SELECT usr_name──────►│
  │                         │◄─────────usuario───────┤
  │                         │                        │
  │                         │  verifica bcrypt       │
  │                         │  genera JWT            │
  │◄──────AccessToken───────┤                        │
  │  (sub, role, exp)       │                        │
```

### Conexión del Robot (Self-Registration con Aprobación)

> Documentación detallada: [`Documents/handshake.md`](./handshake.md)

```
RaspberryPi                API                    Admin              DB
  │                         │                      │                  │
  │  [genera credenciales]  │                      │                  │
  │                         │                      │                  │
  ├─POST /m2m/register─────►│                      │                  │
  │  {ext_id, psw}          ├──INSERT (pending)────────────────────►│
  │◄──200 {pending}─────────┤                      │                  │
  │                         │                      │                  │
  ├─POST /m2m/handshake────►│                      │                  │
  │◄──403 (no aprobado)────┤                      │                  │
  │                         │                      │                  │
  │  [retry con backoff]    │    POST /{id}/approve│                  │
  │                         │◄─────{name, desc}────┤                  │
  │                         ├──UPDATE (approved)──────────────────►│
  │                         │                      │                  │
  ├─POST /m2m/handshake────►│                      │                  │
  │  (HTTP Basic)           │ verifica bcrypt      │                  │
  │                         │ verifica status=approved               │
  │                         │ genera JWT (role=robot)                │
  │◄──{JWT}────────────────┤                      │                  │
  │                         │                      │                  │
  │  [Pi abre WS /m2m/robot/connect → challenge → token → success]    │
```

### Usuario Envía Comando a Robot

```
Usuario                    API                                  RaspberryPi
  │                         │                                      │
  ├─WS /user/send_command──►│                                      │
  │                         │                                      │
  ├─{token, robot_id}──────►│  (auth en 10s)                       │
  │                         │  valida token + robot                │
  │◄───{success auth}───────┤                                      │
  │                         │                                      │
  │                         │  arma pipe UserConn ↔ RobotConn      │
  │                         │  (WS persistente ya abierto)         │
  │                         │                                      │
  ├─{method, params, id}───►│                                      │
  │                         ├──enqueue al WS del robot────────────►│
  │                         │                                      │
  │                         │◄─────────────────{response/status}───┤
  │◄──{response}────────────┤                                      │
```

La RaspberryPi mantiene un WebSocket persistente contra `/m2m/robot/connect`. Al recibir un comando JSON-RPC 2.0 por ese WS, lo ejecuta en el robot y devuelve la respuesta/estado por el mismo canal. La API no transforma el payload — actúa como pipe transparente entre los dos extremos.

---

## Autenticación y Autorización

El sistema usa **tres tipos de tokens JWT**:

| Token | Generado en | `sub` | Campos extra | Uso |
|-------|-------------|-------|-------------|-----|
| **Usuario** | `/auth/login` | usr_name | `role: admin\|user` | Acceso general a la API |
| **Robot access** | `/auth/request_robot_access` | usr_name | `robot_id`, `type: robot_access` | Permiso para controlar un robot específico |
| **Robot** | `/m2m/robot/handshake` | robot UUID | `role: robot`, `scope: broker:*` | Conexión del robot al sistema |

### Flujo de autorización para controlar un robot

1. Usuario se autentica → recibe token de usuario
2. Usuario solicita acceso a un robot → recibe token de robot_access
3. Usuario conecta al WebSocket y envía el token de robot_access
4. En cada comando, envía el `access_token` + `robot_id` → API valida ambos

### Roles

- **`profe`** (admin): Acceso a rutas `/admin/*`, gestión de robots
- **`alumno`** (user): Acceso a rutas `/user/*`, control de robots asignados

---

## Despliegue

El sistema se despliega con **Docker Compose**. Cada subproyecto tiene su propio `Dockerfile` y `compose.yaml` cuando es necesario.

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                         │
│                                                             │
│  ┌───────────┐  ┌──────────┐  ┌───────────┐                 │
│  │ WebClient │  │   API    │  │    DB     │                 │
│  │  (nginx)  │  │(FastAPI) │  │(Postgres) │                 │
│  │  :3000    │  │ :8000    │  │ :5432     │                 │
│  └───────────┘  └──────────┘  └───────────┘                 │
│       │              │              │                       │
│       └──────────────┴──────────────┘                       │
│                       red: ciie-test                        │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐          ┌──────────────┐
│ RaspberryPi  │          │   Arduino    │
│ (en el robot)│──serial──│ (en el robot)│
└──────────────┘          └──────────────┘
```

### Comandos principales (Makefile raíz)

```bash
make up              # DB (background) + API (foreground)
make up.all          # DB + WebClient (background) + API (foreground)
make down            # Detiene todos los servicios en background
make db.migrate      # Ejecuta migraciones
make db.seed         # Aplica datos semilla
make webclient.up    # Frontend Vue (foreground)
```

---

## Modo Demo

El sistema puede ejecutarse **sin hardware físico** para desarrollo y demostración:

- **RaspberryPi**: Usar `MOCK_ROBOT=1` en `.env` para activar el `RobotMockController`, que simula las respuestas del robot sin comunicación serial. Combinado con `CREATE_DEFAULT_METADATA=1`, la Pi se auto-registra y abre el WebSocket contra la API automáticamente
- **Arduino**: No se necesita — el mock de RaspberryPi lo reemplaza
- **Base de datos**: La DB efímera (`make db.up.ephimeral`) usa tmpfs para pruebas rápidas sin persistencia

Toda nueva feature debe garantizar compatibilidad con el modo demo.
