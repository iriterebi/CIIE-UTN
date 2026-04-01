# CLAUDE.md — Quadlets

## Descripción General

Configuración de deploy de producción usando [Podman Quadlets](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html). Los quadlets son archivos declarativos que systemd interpreta para gestionar contenedores Podman como servicios del sistema.

Las imágenes se compilan localmente y se transfieren al servidor via SSH — no se compila nada en el servidor.

## Estructura

```
quadlets/
├── labs-remoto.network         # Red bridge compartida entre servicios
├── db-data.volume              # Volumen persistente para PostgreSQL
├── db.container                # PostgreSQL 17.5-alpine
├── api.container               # FastAPI (imagen: localhost/labs-remoto/api)
├── rosbridge.container         # rosbridge_suite (imagen: localhost/labs-remoto/rosbridge)
├── webclient.container         # SPA Vue 3 + nginx (imagen: localhost/labs-remoto/webclient)
├── proxy.container             # nginx reverse proxy (imagen: localhost/labs-remoto/proxy)
├── deploy.sh                   # Script de build local + deploy via SSH
├── CLAUDE.md
├── README.md
└── README.es.md
```

## Tipos de archivo

| Extensión | Qué hace | Dónde se instala en el servidor |
|-----------|----------|-------------------------------|
| `.container` | Define un contenedor (imagen, red, volúmenes, puertos, dependencias) | `/etc/containers/systemd/` |
| `.network` | Define una red de Podman | `/etc/containers/systemd/` |
| `.volume` | Define un volumen nombrado | `/etc/containers/systemd/` |

## Flujo de deploy

```
[Local]                              [Servidor]
podman build → podman save → scp →   podman load → systemctl restart
```

Todo orquestado por `deploy.sh`:

```bash
./quadlets/deploy.sh usuario@servidor
```

## Red y comunicación entre servicios

Todos los contenedores están en la red `labs-remoto` y se resuelven por hostname:

| Hostname | Servicio | Puerto interno |
|----------|----------|----------------|
| `db` | PostgreSQL | 5432 |
| `api` | FastAPI | 8000 |
| `rosbridge` | rosbridge_suite | 9090 |
| `webclient` | nginx (SPA) | 80 |
| `proxy` | nginx (reverse proxy) | 80 |

Solo el proxy expone el puerto 80 al exterior. Db y rosbridge publican puertos solo en `127.0.0.1` (para migraciones y acceso local).

## Cadena de dependencias (systemd)

```
db ─────────┐
             ├──► api ──────┐
rosbridge ──┘               ├──► proxy
webclient ──────────────────┘
```

`systemctl start proxy` arranca toda la cadena automáticamente.

## Variables de entorno

Los archivos `.env` no están en el repositorio — se configuran manualmente en el servidor:

| Archivo | Ruta en servidor | Variables |
|---------|-----------------|-----------|
| `db.env` | `/etc/containers/env/db.env` | `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` |
| `api.env` | `/etc/containers/env/api.env` | `POSTGRES_*`, `POSTGRES_URL=db:5432`, `ROSBRIDGE_URL=ws://rosbridge:9090`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` |

## Imágenes

| Tag | Dockerfile | Contexto de build |
|-----|------------|-------------------|
| `localhost/labs-remoto/api` | `services/Api/Dockerfile` | Raíz del repo (necesita `pyproject.toml` de raíz) |
| `localhost/labs-remoto/webclient` | `services/WebClient/Dockerfile` | `services/WebClient/` |
| `localhost/labs-remoto/rosbridge` | `services/RosBridge/Dockerfile` | `services/RosBridge/` |
| `localhost/labs-remoto/proxy` | `services/Proxy/Dockerfile` | `services/Proxy/` |

## Proxy (nginx containerizado)

El proxy usa `services/Proxy/nginx.container.conf` (no `services/Proxy/nginx.conf`, que es la versión para host). Diferencias clave:

- Sin TLS (se agregará después)
- Upstreams apuntan a hostnames de contenedores (`api:8000`, `rosbridge:9090`)
- SPA proxeada al contenedor webclient (`proxy_pass http://webclient`) en vez de servir archivos estáticos
- Mantiene restricciones de intranet en `/m2m/` y `/rosbridge/`

## Convenciones

- Los quadlets se instalan en `/etc/containers/systemd/` (rootful)
- Los nombres de servicio en systemd coinciden con el nombre del archivo sin extensión (ej: `api.container` → `systemctl restart api`)
- Los tags de imágenes siempre empiezan con `localhost/labs-remoto/`
- `.build-cache/` es temporal (gitignored) — se crea y elimina durante el deploy
