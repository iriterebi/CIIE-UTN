# CLAUDE.md — WebClient

## Descripción General

SPA en Vue 3 + TypeScript que consume la API FastAPI. Maneja autenticación, listado de robots, control en tiempo real vía WebSocket y panel de administración.

## Ejecución

```bash
npm run dev       # Servidor Vite en :5173 (con proxy a API)
make up_dev       # Docker: nginx en :3000
```

Requiere API + DB corriendo. En dev, Vite proxea `/api` → `http://localhost:8000` y `/ws` para WebSocket.

## Stack

- Vue 3 (Composition API, `<script setup lang="ts">`)
- TypeScript (strict, `vue-tsc` en build)
- Vite (build + dev server + proxy)
- Vue Router (SPA routing + guards)
- Pinia (state management)
- PicoCSS (CSS semántico sin clases)

## Estructura del Código

```
src/
├── main.ts                  # Bootstrap: Pinia, Router, PicoCSS
├── App.vue                  # Layout: NavBar + <RouterView />
├── types.ts                 # Interfaces: Robot
│
├── router/
│   └── index.ts             # Rutas + guards (auth, admin, guest)
│
├── stores/
│   └── auth.ts              # Token JWT (localStorage), User, login/signup/logout
│
├── composables/
│   ├── useApi.ts            # Fetch wrapper: auth header, JSON + form-urlencoded
│   └── useRobotSocket.ts    # WebSocket: connect → auth → send/receive
│
├── pages/
│   ├── LoginPage.vue
│   ├── RegisterPage.vue
│   ├── DashboardPage.vue    # GET /admin/robot/list → RobotCard
│   ├── RobotControlPage.vue # WS /user/robot/send_command
│   ├── AdminRobotsPage.vue  # Pendientes + aprobar/rechazar
│   └── NotFoundPage.vue
│
└── components/
    ├── NavBar.vue
    ├── RobotCard.vue
    ├── RobotCommandPanel.vue
    └── PendingRobotCard.vue
```

## Rutas

| Path | Página | Guard |
|------|--------|-------|
| `/login` | LoginPage | guest (redirige a dashboard si autenticado) |
| `/register` | RegisterPage | guest |
| `/dashboard` | DashboardPage | requiresAuth |
| `/robot/:id` | RobotControlPage | requiresAuth |
| `/admin/robots` | AdminRobotsPage | requiresAuth + requiresAdmin |

## Comunicación con la API

### Auth

- `POST /auth/login` — **form-urlencoded** (`OAuth2PasswordRequestForm`), no JSON
- `POST /auth/signup` — JSON con campos: `nombrecompleto`, `email`, `usr_name`, `usr_psw`, `statuss`, `usr_pronouns`
- `GET /auth/me` — Bearer token → User
- `POST /auth/request_robot_access` — Bearer token + `{"robot_id": "..."}` → AccessToken para controlar robot

### WebSocket (control de robot)

Protocolo de `/user/robot/send_command`:

1. Conectar WS
2. Enviar `{"token": "<robot_access_token>", "robot_id": "<uuid>"}` (timeout 10s del server)
3. Recibir `{"message": "success auth"}`
4. Enviar comandos: `{"method": "<cmd>", "access_token": "<robot_access_token>", "robot_id": "<uuid>"}`
5. Recibir respuestas JSON-RPC

Nota: tanto el `token` del handshake como el `access_token` de los comandos son el
**robot_access token** (de `request_robot_access`), **no** el JWT de sesión del
usuario. El backend valida en el handshake que el token tenga `type: robot_access`
y que su `robot_id`/`sub` coincidan (ver `access_validator.py`). El JWT de sesión de
login solo se usa para las llamadas HTTP (header `Authorization: Bearer`) y los
guards del router.

### Admin

- `GET /admin/robot/list` — Todos los robots
- `GET /admin/robot/pending` — Pendientes de aprobación
- `POST /admin/robot/{id}/approve` — `{"name": "...", "description": "..."}`
- `POST /admin/robot/{id}/reject` — Sin body

Los endpoints admin **no tienen auth** actualmente (WIP en backend).

## Proxy y Networking

### Desarrollo (Vite)

`vite.config.ts` proxea:
- `/api/*` → `http://localhost:8000/*` (rewrite quita `/api`)
- `/ws/*` → `ws://localhost:8000/*` (rewrite quita `/ws`, `ws: true`)

### Producción (nginx)

`nginx.conf`:
- `try_files` → `index.html` (SPA fallback)
- `/api/` → `http://api:8000/` (reverse proxy)
- `/user/robot/` → `http://api:8000/user/robot/` (WS upgrade headers)

## Docker

Multi-stage: `node:22-alpine` (build) → `nginx:alpine` (serve). Puerto 3000, red `ciie-test`, profile `dev`.

## Patrones y Convenciones

- **Composables**: `useApi()` y `useRobotSocket()` encapsulan lógica reutilizable
- **Store Pinia**: setup syntax (función, no options). Token persistido en `localStorage`
- **Props tipados**: `defineProps<{}>()` con interfaces TypeScript
- **Emits tipados**: `defineEmits<{}>()` con nombres de evento y payloads
- **Build**: `vue-tsc -b && vite build` — type check antes de build
