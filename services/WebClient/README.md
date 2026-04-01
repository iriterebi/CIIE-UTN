# WebClient

> [Leer en español](./README.es.md)

Vue 3 + TypeScript frontend for the CIIE Remote Labs project. Single-page application served with nginx in Docker.

## Tech Stack

- **Vue 3** (Composition API + `<script setup>`)
- **TypeScript**
- **Vite** (build + dev server)
- **Vue Router** (SPA routing + auth guards)
- **Pinia** (state management)
- **PicoCSS** (minimal classless CSS framework)

## Quick Start

```bash
npm install
npm run dev       # Vite dev server on :5173
```

The Vite dev server proxies `/api` to `http://localhost:8000` (API) and `/ws` for WebSocket connections. Requires the API and database to be running.

## Docker

```bash
make build        # Build Docker image (multi-stage: node → nginx)
make up_dev       # Run in foreground (port 3000)
make up_dev.detached  # Run in background
make down_dev     # Stop
```

Requires the `ciie-test` Docker network (`docker network create ciie-test`).

## Project Structure

```
src/
├── main.ts                  # App bootstrap: Pinia, Router, PicoCSS
├── App.vue                  # Root layout: NavBar + RouterView
├── types.ts                 # Shared interfaces (Robot, etc.)
├── router/
│   └── index.ts             # Routes + navigation guards (auth, admin)
├── stores/
│   └── auth.ts              # Auth store: JWT token, user, login/signup/logout
├── composables/
│   ├── useApi.ts            # Fetch wrapper: auth headers, JSON + form-urlencoded
│   └── useRobotSocket.ts    # WebSocket: connect, auth, send commands, receive responses
├── pages/
│   ├── LoginPage.vue        # Username + password login
│   ├── RegisterPage.vue     # User registration form
│   ├── DashboardPage.vue    # Robot list, request access, navigate to control
│   ├── RobotControlPage.vue # WebSocket connection + command panel
│   ├── AdminRobotsPage.vue  # Pending robots, approve/reject
│   └── NotFoundPage.vue
└── components/
    ├── NavBar.vue
    ├── RobotCard.vue
    ├── RobotCommandPanel.vue
    └── PendingRobotCard.vue
```

## Routes

| Path | Page | Auth | Role |
|------|------|------|------|
| `/login` | LoginPage | No | — |
| `/register` | RegisterPage | No | — |
| `/dashboard` | DashboardPage | Yes | user/admin |
| `/robot/:id` | RobotControlPage | Yes | user/admin |
| `/admin/robots` | AdminRobotsPage | Yes | admin |

## Environment Variables

Configured via `.env.development` and `.env.production`:

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE` | API base path (default: `/api`) |
| `VITE_WS_BASE` | WebSocket base path (default: `/ws` in dev, empty in prod) |
