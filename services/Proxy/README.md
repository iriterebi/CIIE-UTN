# Proxy — nginx

[Leer en español](README.es.md)

Main reverse proxy for the Labs Remoto deployment server. nginx is the only component installed directly on the host (not in Docker) — it serves as the single entry point for all traffic.

## Responsibilities

1. **Reverse proxy** — routes HTTP and WebSocket traffic to internal Docker services
2. **Static file server** — serves the Vue 3 SPA
3. **TLS termination** — handles SSL certificates (Let's Encrypt)
4. **Access control** — restricts the internal `/m2m` route (registration, handshake, and robot WS) to intranet IPs

## Architecture

```
INTERNET ──► nginx (:443) ──► API (:8000)          [Docker]
INTRANET ──►               ──► SPA (static files)  [host filesystem]
```

- Users (internet) access the SPA, REST API, and user WebSocket
- RaspberryPis (intranet) access `/m2m/*` for registration, handshake, and WebSocket (`/m2m/robot/connect`)
- Docker services publish ports only on `127.0.0.1` — nginx is the only externally reachable component

## Route Map

| Path | Destination | Type | Access |
|------|-------------|------|--------|
| `/` | SPA (Vue 3 static files) | HTTP | Public |
| `/api/*` | API (:8000), strips `/api` prefix | HTTP | Public |
| `/ws/*` | API (:8000), WebSocket upgrade | WebSocket | Public |
| `/m2m/*` | API (:8000), includes WebSocket upgrade on `/m2m/robot/connect` | HTTP + WebSocket | Intranet only |

## Setup

### Install nginx

```bash
sudo apt install nginx
```

### Install configuration

```bash
sudo cp nginx.conf /etc/nginx/sites-available/labs-remoto
sudo ln -s /etc/nginx/sites-available/labs-remoto /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### TLS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMAIN>
```

certbot modifies the nginx config automatically and sets up auto-renewal.

### Deploy the SPA

```bash
cd ../WebClient && npm ci && npm run build
sudo mkdir -p /var/www/labs-remoto
sudo cp -r dist/* /var/www/labs-remoto/
```

## Why nginx Is Not in Docker

- It's the entry point to the server — managing TLS, certificates, and network is simpler without the Docker layer
- Needs direct access to host ports 80/443
- certbot integration and auto-renewal work more naturally on the host
- All other services run in Docker — nginx is the exception

## Why nginx over HAProxy

See [Documents/red_y_despliegue.md](../../Documents/red_y_despliegue.md) for the full comparison. Summary: nginx serves the SPA natively, has simpler path-based routing, and integrates with certbot out of the box. HAProxy's advantages (advanced load balancing, circuit breaking) aren't needed at this scale.
