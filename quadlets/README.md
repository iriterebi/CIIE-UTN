# Quadlets — Production Deployment with Podman

[Español](README.es.md)

[Podman Quadlets](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) configuration to deploy Labs Remoto in production. Each service runs as a systemd-managed container.

## Architecture

```
Internet → [:80] Proxy (nginx) → API (FastAPI) → RosBridge (ROS 2)
                                → WebClient (Vue 3 + nginx)
                    ↕
                 PostgreSQL
```

All services communicate through an internal Podman network (`labs-remoto`). Only the proxy exposes port 80 externally.

## Services

| Service | File | Image | External Port |
|---------|------|-------|---------------|
| **Db** | `db.container` | `postgres:17.5-alpine` | `127.0.0.1:5432` |
| **Api** | `api.container` | `localhost/labs-remoto/api` | — |
| **RosBridge** | `rosbridge.container` | `localhost/labs-remoto/rosbridge` | `127.0.0.1:9090` |
| **WebClient** | `webclient.container` | `localhost/labs-remoto/webclient` | — |
| **Proxy** | `proxy.container` | `localhost/labs-remoto/proxy` | `80` |

## Prerequisites

- Podman 4.4+ (Quadlet support)
- Root access (quadlets are installed in `/etc/containers/systemd/`)

## Installation

### 1. Configure environment variables

Create environment files in `/etc/containers/env/`:

```bash
sudo mkdir -p /etc/containers/env
```

**`/etc/containers/env/db.env`**:
```env
POSTGRES_PASSWORD=<secure_password>
POSTGRES_USER=<user>
POSTGRES_DB=ciie_db
```

**`/etc/containers/env/api.env`**:
```env
POSTGRES_PASSWORD=<secure_password>
POSTGRES_USER=<user>
POSTGRES_DB=ciie_db
POSTGRES_URL=db:5432
ROSBRIDGE_URL=ws://rosbridge:9090
JWT_SECRET_KEY=<secret_key>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 2. Copy quadlets to the server

```bash
sudo cp quadlets/*.container quadlets/*.network quadlets/*.volume \
    /etc/containers/systemd/
sudo systemctl daemon-reload
```

### 3. Deploy images

Images are built locally and transferred to the server via SSH using `deploy.sh`:

```bash
./quadlets/deploy.sh user@server
```

The script builds the 4 images (api, webclient, rosbridge, proxy), exports them to `.tar`, transfers them via `scp`, loads them with `podman load` on the server, and restarts all services.

### 4. First start (if deploy.sh was not used)

```bash
# On the server: start the full dependency chain
sudo systemctl start proxy
```

## Common Operations

```bash
# Check status of all services
sudo systemctl status db api rosbridge webclient proxy

# Follow logs for a service
sudo journalctl -u api -f

# Restart a service
sudo systemctl restart api

# Stop everything
sudo systemctl stop proxy api webclient rosbridge db

# Redeploy after code changes
./quadlets/deploy.sh user@server
```

## Dependency Chain

```
db ─────────┐
             ├──► api ──────┐
rosbridge ──┘               ├──► proxy
webclient ──────────────────┘
```

`systemctl start proxy` automatically starts all required services in the correct order.

## Database Migrations

The database is accessible at `127.0.0.1:5432` for running migrations with dbmate:

```bash
cd Db
DATABASE_URL="postgres://<user>:<password>@127.0.0.1:5432/ciie_db?sslmode=disable" \
    dbmate up
```

## Notes

- **No TLS**: this configuration does not include TLS. For production with HTTPS, add an external reverse proxy with certbot or mount certificates into the proxy container.
- **Intranet**: routes `/m2m/` and `/rosbridge/` are restricted to private IPs in the nginx configuration. Verify that restrictions work correctly with Podman networking.
- **Logs**: use `journalctl -u <service>` to view logs, as systemd captures container stdout/stderr.
