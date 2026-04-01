# WebClient

> [Read in English](./README.md)

Frontend Vue 3 + TypeScript para el proyecto CIIE Labs Remoto. Aplicación de página única (SPA) servida con nginx en Docker.

## Stack Tecnológico

- **Vue 3** (Composition API + `<script setup>`)
- **TypeScript**
- **Vite** (build + servidor de desarrollo)
- **Vue Router** (routing SPA + guards de auth)
- **Pinia** (gestión de estado)
- **PicoCSS** (framework CSS minimalista sin clases)

## Inicio Rápido

```bash
npm install
npm run dev       # Servidor Vite en :5173
```

El servidor de Vite hace proxy de `/api` hacia `http://localhost:8000` (API) y `/ws` para conexiones WebSocket. Requiere la API y la base de datos corriendo.

## Docker

```bash
make build        # Construir imagen Docker (multi-stage: node → nginx)
make up_dev       # Ejecutar en foreground (puerto 3000)
make up_dev.detached  # Ejecutar en background
make down_dev     # Detener
```

Requiere la red Docker `ciie-test` (`docker network create ciie-test`).

## Estructura del Proyecto

```
src/
├── main.ts                  # Bootstrap: Pinia, Router, PicoCSS
├── App.vue                  # Layout raíz: NavBar + RouterView
├── types.ts                 # Interfaces compartidas (Robot, etc.)
├── router/
│   └── index.ts             # Rutas + navigation guards (auth, admin)
├── stores/
│   └── auth.ts              # Store de auth: token JWT, usuario, login/signup/logout
├── composables/
│   ├── useApi.ts            # Wrapper fetch: headers de auth, JSON + form-urlencoded
│   └── useRobotSocket.ts    # WebSocket: conectar, auth, enviar comandos, recibir respuestas
├── pages/
│   ├── LoginPage.vue        # Login con usuario y contraseña
│   ├── RegisterPage.vue     # Formulario de registro
│   ├── DashboardPage.vue    # Lista de robots, solicitar acceso, navegar a control
│   ├── RobotControlPage.vue # Conexión WebSocket + panel de comandos
│   ├── AdminRobotsPage.vue  # Robots pendientes, aprobar/rechazar
│   └── NotFoundPage.vue
└── components/
    ├── NavBar.vue
    ├── RobotCard.vue
    ├── RobotCommandPanel.vue
    └── PendingRobotCard.vue
```

## Rutas

| Ruta | Página | Auth | Rol |
|------|--------|------|-----|
| `/login` | LoginPage | No | — |
| `/register` | RegisterPage | No | — |
| `/dashboard` | DashboardPage | Sí | user/admin |
| `/robot/:id` | RobotControlPage | Sí | user/admin |
| `/admin/robots` | AdminRobotsPage | Sí | admin |

## Variables de Entorno

Configuradas en `.env.development` y `.env.production`:

| Variable | Descripción |
|----------|-------------|
| `VITE_API_BASE` | Path base de la API (default: `/api`) |
| `VITE_WS_BASE` | Path base WebSocket (default: `/ws` en dev, vacío en prod) |
