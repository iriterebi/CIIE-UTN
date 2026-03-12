# Arquitectura del Sistema — Labs Remoto

## Índice

- [Visión General](#visión-general)
- [Diagrama de Arquitectura](#diagrama-de-arquitectura)
- [Componentes](#componentes)
  - [Frontend](#frontend)
  - [API (Backend)](#api-backend)
  - [Base de Datos](#base-de-datos)
  - [ROS](#ros)
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

El sistema sigue una arquitectura de **capas lineales** con la API como punto central de orquestación:

```
Usuario → Frontend → API → ROS → RaspberryPi → Arduino → Robot Físico
```

---

## Diagrama de Arquitectura

```
┌─────────────┐
│  Frontend   │  Interfaz web de control
│  (por       │
│  construir) │
└──────┬──────┘
       │ HTTP / WebSocket
       ▼
┌─────────────┐         ┌─────────────┐
│    API      │◄───────►│ PostgreSQL  │
│  (FastAPI)  │         │   17.5      │
│             │         └─────────────┘
│  - Auth     │
│  - Sesiones │
│  - IPC      │
└──────┬──────┘
       │ (futuro: ROS)
       │ (actual: HTTP/WS directo)
       ▼
┌─────────────┐
│    ROS      │  Gestión y control de robots
│  (ROS 2     │
│   Humble)   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ RaspberryPi │  Un controlador por robot
│ (Python)    │
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

- **Estado**: Por construir (el frontend viejo en PHP en `Web/` está deprecado)
- **Responsabilidad**: Interfaz de usuario para autenticación, selección de robot y envío de comandos de control
- **Comunicación con API**: HTTP para auth, WebSocket para comandos en tiempo real

### API (Backend)

- **Directorio**: `Api/`
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
| `robot` (m2m) | `/m2m/robot/*` | Handshake y WebSocket para robots |
| `robot` (user) | `/user/robot/*` | WebSocket para usuarios |

#### IPC (Bus de Mensajes Interno)

La API usa un `AsyncSubject` (aioreactive) como bus interno de mensajes:

```
Usuario ──WS──► UserToRobotCommunication ──► AsyncSubject ──► RobotConnection ──WS──► Robot
                                                  ▲                    │
                                                  └────────────────────┘
                                                  (respuestas del robot)
```

- Los comandos del usuario se publican al subject con el `robot_id` destino
- Cada `RobotConnection` se suscribe filtrando por su `robot_id`
- Las respuestas del robot se emiten de vuelta al subject

### Base de Datos

- **Directorio**: `Db/`
- **Tecnología**: PostgreSQL 17.5 (Alpine)
- **Migraciones**: dbmate
- **Responsabilidad**: Persistencia de usuarios, robots y auditoría de cambios de estado

### ROS

- **Directorio**: `ros_tryouts/`
- **Tecnología**: ROS 2 Humble
- **Responsabilidad**: Gestión y control de robots a nivel de sistema operativo robótico
- **Estado**: En desarrollo por otro miembro del equipo — no lo modificamos

### RaspberryPi (Controlador del Robot)

- **Directorio**: `RaspberryPi/`
- **Tecnología**: Python 3.13.7+
- **Responsabilidad**: Se ejecuta en cada robot físico. Maneja:
  - Conexión con la API (handshake HTTP Basic → JWT → WebSocket)
  - Recepción de comandos desde la API
  - Traducción de comandos a instrucciones seriales para Arduino
  - Reporte de estado (futuro)
- **Mock disponible**: `RobotMockController` (activable con `MOCK_ROBOT=1`) para desarrollo sin hardware

### Arduino (Firmware)

- **Directorio**: `Arduino/`
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
│ email (unique)   │   │   │ name                 │
│ usr_name (unique)│   └───┤ user_id (FK)         │
│ usr_psw (bcrypt) │       │ psw (bcrypt)         │
│ statuss (enum)   │       │ status               │
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
- **RaspberryPi → API**: Handshake inicial (`POST /m2m/robot/handshake` con HTTP Basic)

### WebSocket

- **Frontend → API** (`/user/robot/send_command`): Canal bidireccional para envío de comandos y recepción de respuestas del robot
- **API → RaspberryPi** (`/m2m/robot/commands/{token}`): Canal bidireccional para envío de comandos al robot y recepción de respuestas

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

### Conexión del Robot

```
RaspberryPi                API                      DB
  │                         │                        │
  ├─POST /m2m/handshake────►│                        │
  │  (HTTP Basic:           ├──SELECT ext_id────────►│
  │   ext_id + password)    │◄─────────robot─────────┤
  │                         │                        │
  │                         │ verifica bcrypt        │
  │                         │ genera JWT (role=robot)│
  │◄──────AccessToken───────┤                        │
  │                         │                        │
  ├─WS /m2m/commands/{jwt}─►│                        │
  │                         │ valida JWT             │
  │◄──────WS accepted───────┤                        │
  │                         │ suscribe a IPC subject │
  │         (conexión persistente bidireccional)     │
```

### Usuario Envía Comando a Robot

```
Usuario                    API                      RaspberryPi
  │                         │                        │
  ├─WS /user/send_command──►│                        │
  │                         │◄──WS accepted──────────│
  │                         │                        │
  ├─{token}────────────────►│  (auth en 10s)         │
  │                         │  valida token          │
  │◄───{success auth}───────┤                        │
  │                         │                        │
  ├─{method, robot_id,─────►│                        │
  │  access_token}          │ valida robot existe    │
  │                         │ valida access_token    │
  │                         │ publica al IPC subject │
  │                         │                        │
  │                         ├──{command}────────────►│
  │                         │ (filtrado por robot_id)│
  │                         │                        │
  │                         │◄──{response}───────────┤
  │◄──{response}────────────┤  (futuro)              │
```

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
┌────────────────────────────────────────────┐
│              Docker Compose                │
│                                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │   API    │  │   DB     │  │   Web    │  │
│  │ (FastAPI)│  │(Postgres)│  │  (PHP)   │  │
│  │ :8000    │  │ :5432    │  │  :8080   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
│         │              │                   │
│         └──────────────┘                   │
│           red: ciie-test                   │
└────────────────────────────────────────────┘

┌──────────────┐          ┌──────────────┐
│ RaspberryPi  │          │   Arduino    │
│ (en el robot)│──serial──│ (en el robot)│
└──────────────┘          └──────────────┘
```

### Comandos principales (Makefile raíz)

```bash
make up          # DB (background) + API (foreground)
make up.all      # DB + Web (background) + API (foreground)
make down        # Detiene todos los servicios en background
make db.migrate  # Ejecuta migraciones
make db.seed     # Aplica datos semilla
```

---

## Modo Demo

El sistema puede ejecutarse **sin hardware físico** para desarrollo y demostración:

- **RaspberryPi**: Usar `MOCK_ROBOT=1` en `.env` para activar el `RobotMockController`, que simula las respuestas del robot sin comunicación serial
- **Arduino**: No se necesita — el mock de RaspberryPi lo reemplaza
- **Base de datos**: La DB efímera (`make db.up.ephimeral`) usa tmpfs para pruebas rápidas sin persistencia

Toda nueva feature debe garantizar compatibilidad con el modo demo.
