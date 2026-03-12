# Handshake de Robots — Registro y Aprobación

## Índice

- [Visión General](#visión-general)
- [Flujo Completo](#flujo-completo)
  - [1. Generación de Credenciales](#1-generación-de-credenciales)
  - [2. Registro (Self-Registration)](#2-registro-self-registration)
  - [3. Espera de Aprobación](#3-espera-de-aprobación)
  - [4. Aprobación por Admin](#4-aprobación-por-admin)
  - [5. Handshake Exitoso](#5-handshake-exitoso)
  - [6. Conexión WebSocket](#6-conexión-websocket)
- [Diagrama de Secuencia](#diagrama-de-secuencia)
- [Estados del Robot](#estados-del-robot)
- [Endpoints Involucrados](#endpoints-involucrados)
- [Seguridad](#seguridad)
- [Re-registro (Idempotencia)](#re-registro-idempotencia)
- [Rechazo](#rechazo)
- [Modo Demo](#modo-demo)

---

## Visión General

El sistema usa un modelo **híbrido de self-registration con aprobación administrativa**. Los robots se auto-registran al arrancar, pero no pueden operar hasta que un administrador los apruebe y les asigne un nombre.

Este diseño equilibra:
- **Autonomía**: los robots no requieren pre-configuración manual en el servidor
- **Control**: un admin valida cada robot antes de que pueda recibir comandos

---

## Flujo Completo

### 1. Generación de Credenciales

Al arrancar por primera vez, la RaspberryPi genera un archivo `robot-metadata.json` con credenciales únicas:

```json
{
    "robot_id": "550e8400-e29b-41d4-a716-446655440000",
    "robot_psw": "aB3$kL9mP2xQ...(24 chars)",
    "creation_time": 1710200000
}
```

- `robot_id` es un UUID v4 aleatorio — actúa como **identificador interno** (análogo a un username)
- `robot_psw` es una contraseña aleatoria de 24 caracteres (letras, dígitos, símbolos)
- Este archivo se persiste en el filesystem de la Pi y no se versiona

Controlado por la variable `CREATE_DEFAUL_METADATA=1`.

### 2. Registro (Self-Registration)

La Pi envía sus credenciales al servidor:

```
POST /m2m/robot/register
Content-Type: application/json

{
    "external_identifier": "550e8400-e29b-41d4-a716-446655440000",
    "psw": "aB3$kL9mP2xQ..."
}
```

**Respuesta** (200):
```json
{
    "external_identifier": "550e8400-e29b-41d4-a716-446655440000",
    "status": "pending_approval"
}
```

El servidor:
- Hashea la contraseña con bcrypt
- Crea el robot en DB con `status=pending_approval` y `name=null`
- Registra el cambio de estado en `robot_status_history` (trigger automático)

### 3. Espera de Aprobación

Inmediatamente después del registro, la Pi intenta el handshake:

```
POST /m2m/robot/handshake
Authorization: Basic <base64(external_identifier:password)>
```

**Respuesta** (403):
```json
{
    "detail": "Robot no aprobado. Estado actual: pending_approval"
}
```

La Pi entra en un **loop de reintento con backoff exponencial**:

| Intento | Espera |
|---------|--------|
| 1 | 5s |
| 2 | 10s |
| 3 | 20s |
| 4 | 40s |
| ... | ... |
| n | min(5 × 2^n, 300s) |

El delay máximo es **5 minutos**. El loop es infinito — la Pi no tiene otra tarea hasta ser aprobada.

### 4. Aprobación por Admin

Un administrador ve los robots pendientes y aprueba asignando nombre y descripción:

```
GET /admin/robot/pending
```

```json
[
    {
        "id": "a1b2c3d4-...",
        "external_identifier": "550e8400-...",
        "name": null,
        "status": "pending_approval"
    }
]
```

```
POST /admin/robot/a1b2c3d4-.../approve
Content-Type: application/json

{
    "name": "Brazo Lab 1",
    "description": "Robot del laboratorio de mecatrónica"
}
```

**Respuesta** (200):
```json
{
    "id": "a1b2c3d4-...",
    "external_identifier": "550e8400-...",
    "name": "Brazo Lab 1",
    "description": "Robot del laboratorio de mecatrónica",
    "status": "approved"
}
```

### 5. Handshake Exitoso

En el siguiente reintento de la Pi, el handshake retorna un JWT:

```
POST /m2m/robot/handshake
Authorization: Basic <base64(external_identifier:password)>
```

**Respuesta** (200):
```json
{
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "scope": "broker:report_log broker:listen_commands",
    "expires_in": 3600
}
```

El JWT contiene:
- `sub`: UUID interno del robot (asignado por el sistema, no el `external_identifier`)
- `role`: `"robot"`
- `scope`: permisos del robot

### 6. Conexión WebSocket

Con el JWT, la Pi abre una conexión WebSocket persistente:

```
WS /m2m/robot/commands/<jwt_token>
```

A partir de aquí, el robot recibe comandos JSON-RPC de los usuarios a través del bus IPC interno de la API.

---

## Diagrama de Secuencia

```
RaspberryPi              API                    Admin              DB
    │                      │                      │                 │
    │  [Arranque]          │                      │                 │
    │  genera metadata     │                      │                 │
    │                      │                      │                 │
    ├──POST /register─────►│                      │                 │
    │  {ext_id, psw}       ├──INSERT robot───────────────────────►│
    │                      │  status=pending      │                 │
    │◄──200 {pending}──────┤                      │                 │
    │                      │                      │                 │
    ├──POST /handshake────►│                      │                 │
    │  (HTTP Basic)        │  status != approved  │                 │
    │◄──403 {no aprobado}──┤                      │                 │
    │                      │                      │                 │
    │  [espera 5s]         │                      │                 │
    │                      │                      │                 │
    ├──POST /handshake────►│                      │                 │
    │◄──403────────────────┤                      │                 │
    │                      │                      │                 │
    │  [espera 10s]        │  ┌───────────────────┤                 │
    │                      │  │ GET /pending      │                 │
    │                      │  │◄──lista robots────┤                 │
    │                      │  │                   │                 │
    │                      │  │ POST /{id}/approve│                 │
    │                      │  │ {name, desc}      │                 │
    │                      │◄─┤                   │                 │
    │                      ├──UPDATE status=approved──────────────►│
    │                      │  └──200 {approved}──►│                 │
    │                      │                      │                 │
    ├──POST /handshake────►│                      │                 │
    │  (HTTP Basic)        │  status == approved  │                 │
    │◄──200 {JWT}──────────┤                      │                 │
    │                      │                      │                 │
    ├──WS /commands/{jwt}─►│                      │                 │
    │◄──WS accepted────────┤                      │                 │
    │   (bidireccional)    │                      │                 │
```

---

## Estados del Robot

| Estado | Significado | Transiciones posibles |
|--------|-------------|----------------------|
| `pending_approval` | Registrado, esperando aprobación | → `approved`, → `rejected` |
| `approved` | Aprobado, puede hacer handshake y operar | → `disabled` |
| `rejected` | Rechazado por el admin | (terminal por ahora) |
| `disabled` | Deshabilitado administrativamente | → `approved` |

Constraint en DB: `CHECK (status IN ('pending_approval', 'approved', 'rejected', 'disabled'))`.

Cada cambio de estado se registra automáticamente en `robot_status_history` vía trigger.

---

## Endpoints Involucrados

### Registro (M2M — interno)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `POST` | `/m2m/robot/register` | Ninguna (red interna) | Auto-registro del robot |
| `POST` | `/m2m/robot/handshake` | HTTP Basic | Obtener JWT (solo si aprobado) |
| `WS` | `/m2m/robot/commands/{token}` | JWT en URL | Canal de comandos |

### Administración

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| `GET` | `/admin/robot/pending` | Admin (WIP) | Listar robots pendientes |
| `POST` | `/admin/robot/{id}/approve` | Admin (WIP) | Aprobar robot (asignar nombre) |
| `POST` | `/admin/robot/{id}/reject` | Admin (WIP) | Rechazar robot |

---

## Seguridad

- **`/register` es interno**: No está expuesto al público. El acceso se restringe a nivel de red (proxy/firewall). A nivel de aplicación no requiere autenticación
- **Contraseñas hasheadas**: La contraseña del robot se almacena en DB con bcrypt. Solo la Pi tiene la contraseña en texto plano (en `robot-metadata.json`)
- **Handshake gate**: Robots no aprobados reciben 403 — no pueden obtener JWT ni conectarse al WebSocket
- **`external_identifier` como username**: El UUID generado por la Pi actúa como identificador interno. El `id` real del robot (UUID asignado por PostgreSQL) es el que se usa en tokens JWT y en la lógica del sistema

---

## Re-registro (Idempotencia)

Si una Pi con credenciales existentes intenta registrarse de nuevo (por reinicio, re-deploy, etc.):

- El servidor detecta que el `external_identifier` ya existe
- Retorna el robot existente sin modificar nada
- No se crea duplicado, no se cambia el estado
- La respuesta incluye el estado actual (`pending_approval`, `approved`, etc.)

Esto permite que la Pi llame a `/register` en cada arranque sin efectos secundarios.

---

## Rechazo

Si un admin rechaza un robot:

```
POST /admin/robot/{id}/reject
```

- El estado cambia a `rejected`
- La Pi seguirá recibiendo 403 en el handshake
- El re-registro retorna el robot existente con `status=rejected` (no lo resetea a `pending_approval`)

---

## Modo Demo

Para probar el flujo completo sin hardware:

1. Iniciar DB: `cd Db && make up_db.dev.detached && make migrate_db`
2. Iniciar API: `cd Api && make up_dev`
3. Simular registro: `curl -X POST http://localhost:8000/m2m/robot/register -H 'Content-Type: application/json' -d '{"external_identifier": "550e8400-e29b-41d4-a716-446655440000", "psw": "test123"}'`
4. Ver pendientes: `curl http://localhost:8000/admin/robot/pending`
5. Aprobar: `curl -X POST http://localhost:8000/admin/robot/{id}/approve -H 'Content-Type: application/json' -d '{"name": "Demo Robot"}'`
6. Handshake: `curl -X POST http://localhost:8000/m2m/robot/handshake -u '550e8400-e29b-41d4-a716-446655440000:test123'`

Con la Pi en modo mock (`MOCK_ROBOT=1`, `CREATE_DEFAUL_METADATA=1`), el flujo completo se ejecuta automáticamente — solo falta la aprobación manual del admin.
