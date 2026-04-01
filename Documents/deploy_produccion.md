# Deploy de Producción — Podman Quadlets

## Índice

- [Visión General](#visión-general)
- [Tecnologías](#tecnologías)
  - [Podman](#podman)
  - [Quadlets](#quadlets)
  - [systemd](#systemd)
- [Arquitectura de Deploy](#arquitectura-de-deploy)
  - [Diagrama](#diagrama)
  - [Diferencias con el entorno de desarrollo](#diferencias-con-el-entorno-de-desarrollo)
- [Estructura de Archivos](#estructura-de-archivos)
  - [Quadlets](#quadlets-archivos)
  - [Archivos de soporte](#archivos-de-soporte)
- [Los 5 Servicios](#los-5-servicios)
  - [db — PostgreSQL](#db--postgresql)
  - [api — FastAPI](#api--fastapi)
  - [rosbridge — RosBridge](#rosbridge--rosbridge)
  - [webclient — SPA Vue 3](#webclient--spa-vue-3)
  - [proxy — nginx reverse proxy](#proxy--nginx-reverse-proxy)
- [Red y Comunicación](#red-y-comunicación)
- [Cadena de Dependencias](#cadena-de-dependencias)
- [Variables de Entorno](#variables-de-entorno)
- [Proceso de Deploy](#proceso-de-deploy)
  - [Setup inicial del servidor](#setup-inicial-del-servidor)
  - [Deploy con el script](#deploy-con-el-script)
  - [Flujo completo](#flujo-completo)
  - [Flujo parcial](#flujo-parcial)
- [El Script deploy.sh](#el-script-deploysh)
  - [Sintaxis](#sintaxis)
  - [Modos de operación](#modos-de-operación)
  - [Ejemplos](#ejemplos)
- [Operaciones Comunes](#operaciones-comunes)
- [Diferencias con el Proxy en Host](#diferencias-con-el-proxy-en-host)

---

## Visión General

El deploy de producción usa **Podman Quadlets** para correr los 5 servicios del sistema como contenedores gestionados por systemd. Las imágenes se compilan localmente en la máquina del desarrollador y se transfieren al servidor vía SSH — no se compila nada en el servidor.

```
[Dev local]                                [Servidor]
 podman build → podman save → scp ──────►  podman load → systemctl restart
```

Todos los archivos de configuración están en la carpeta `quadlets/` del repositorio.

---

## Tecnologías

### Podman

[Podman](https://podman.io/) es un motor de contenedores compatible con Docker pero sin daemon. Cada contenedor corre como un proceso independiente del sistema, lo que facilita la integración con systemd.

Diferencias principales con Docker para este proyecto:
- **Sin daemon**: no hay un servicio `dockerd` corriendo. Cada contenedor es un proceso directo
- **Integración nativa con systemd**: los contenedores se gestionan como servicios del sistema (`systemctl start`, `systemctl stop`, `journalctl`)
- **Compatibilidad con Dockerfile**: los mismos Dockerfiles que usamos en desarrollo funcionan sin cambios

### Quadlets

Los [Quadlets](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) son archivos declarativos que Podman traduce a unidades de systemd. En lugar de escribir archivos `.service` de systemd manualmente, escribimos archivos `.container`, `.network` y `.volume` con una sintaxis más simple y específica para contenedores.

Tipos de archivo:

| Extensión | Qué describe | Ejemplo |
|-----------|-------------|---------|
| `.container` | Un contenedor: imagen, puertos, volúmenes, red, dependencias | `api.container` |
| `.network` | Una red de Podman donde los contenedores se resuelven por nombre | `labs-remoto.network` |
| `.volume` | Un volumen nombrado para persistencia de datos | `db-data.volume` |

Los archivos se instalan en `/etc/containers/systemd/` (para servicios de sistema) y Podman los convierte automáticamente en unidades de systemd al ejecutar `systemctl daemon-reload`.

### systemd

systemd gestiona el ciclo de vida de los contenedores: arranque automático, reinicio ante fallos, orden de dependencias y logs centralizados. Los contenedores se operan con los mismos comandos que cualquier servicio de Linux:

```bash
systemctl start api          # Arrancar
systemctl stop api           # Detener
systemctl restart api        # Reiniciar
systemctl status api         # Ver estado
journalctl -u api -f         # Seguir logs
```

---

## Arquitectura de Deploy

### Diagrama

```
                    INTERNET                          INTRANET
                       │                                 │
                       ▼                                 ▼
               ┌──────────────────────────────────────────────┐
               │              Podman (red: labs-remoto)        │
               │                                              │
               │  ┌─────────────────────────────────────────┐ │
               │  │             proxy (nginx)                │ │
               │  │               :80                        │ │
               │  └──┬──────────┬──────────┬────────────────┘ │
               │     │          │          │                   │
               │     ▼          ▼          ▼                   │
               │  ┌───────┐ ┌──────┐ ┌───────────┐            │
               │  │  api  │ │ web  │ │ rosbridge │            │
               │  │:8000  │ │client│ │   :9090   │            │
               │  └───┬───┘ │ :80  │ └───────────┘            │
               │      │     └──────┘                           │
               │      ▼                                        │
               │  ┌──────┐                                     │
               │  │  db  │                                     │
               │  │:5432 │                                     │
               │  └──────┘                                     │
               └──────────────────────────────────────────────┘
```

### Diferencias con el entorno de desarrollo

| Aspecto | Desarrollo | Producción |
|---------|-----------|------------|
| **Orquestador** | Docker Compose | Podman Quadlets + systemd |
| **Red** | `ciie-test` (Docker network) | `labs-remoto` (Podman network) |
| **Proxy/nginx** | Instalado en el host | Containerizado |
| **SPA** | Vite dev server (:5173) o nginx (:3000) | nginx en contenedor webclient, proxeado por proxy |
| **TLS** | No | No (por ahora — se agrega después) |
| **Build** | Docker build en cada máquina | Build local → transfer SSH → podman load |
| **Puertos expuestos** | Todos los servicios publican puertos | Solo proxy (:80), db y rosbridge en 127.0.0.1 |
| **Env vars** | `.env` en cada subproyecto | `/etc/containers/env/` en el servidor |

---

## Estructura de Archivos

### Quadlets (archivos)

```
quadlets/
├── labs-remoto.network         # Red compartida entre todos los servicios
├── db-data.volume              # Volumen persistente para PostgreSQL
├── db.container                # PostgreSQL 17.5-alpine
├── api.container               # FastAPI
├── rosbridge.container         # rosbridge_suite (ROS 2)
├── webclient.container         # SPA Vue 3 + nginx
├── proxy.container             # nginx reverse proxy (punto de entrada)
├── deploy.sh                   # Script de build + deploy via SSH
├── CLAUDE.md
├── README.md
└── README.es.md
```

### Archivos de soporte

Además de los quadlets, hay dos archivos en `services/Proxy/` para la versión containerizada del proxy:

| Archivo | Descripción |
|---------|-------------|
| `services/Proxy/Dockerfile` | `nginx:alpine` con la config de producción |
| `services/Proxy/nginx.container.conf` | nginx.conf adaptada para red de contenedores |

La config original `services/Proxy/nginx.conf` se mantiene como referencia de la versión para host (con TLS, archivos estáticos, etc.).

---

## Los 5 Servicios

### db — PostgreSQL

- **Imagen**: `postgres:17.5-alpine` (no se compila, se usa directamente)
- **Volumen**: `db-data.volume` montado en `/var/lib/postgresql/data`
- **Puerto**: `127.0.0.1:5432` (solo localhost, para ejecutar migraciones con dbmate)
- **Env file**: `/etc/containers/env/db.env`
- **Healthcheck**: `pg_isready` cada 5 segundos

### api — FastAPI

- **Imagen**: `localhost/labs-remoto/api` (compilada desde `services/Api/Dockerfile`)
- **Contexto de build**: raíz del repositorio (necesita `pyproject.toml` de raíz + `services/Api/`)
- **Puerto**: no publicado — solo accesible por el proxy a través de la red interna
- **Env file**: `/etc/containers/env/api.env`
- **Depende de**: db, rosbridge

### rosbridge — RosBridge

- **Imagen**: `localhost/labs-remoto/rosbridge` (compilada desde `services/RosBridge/Dockerfile`)
- **Puerto**: `127.0.0.1:9090` (localhost para acceso de las RaspberryPi vía proxy)
- **Environment**: `ROS_DOMAIN_ID=0`
- **Comando**: `ros2 launch /ros_bridge_ws/launch/bridge.launch.py`

### webclient — SPA Vue 3

- **Imagen**: `localhost/labs-remoto/webclient` (compilada desde `services/WebClient/Dockerfile`)
- **Build**: multi-stage — `node:22-alpine` compila la SPA, `nginx:alpine` la sirve
- **Puerto**: no publicado — solo accesible por el proxy
- **Sin env file**: las variables de Vite (`VITE_*`) se resuelven en tiempo de compilación

### proxy — nginx reverse proxy

- **Imagen**: `localhost/labs-remoto/proxy` (compilada desde `services/Proxy/Dockerfile`)
- **Puerto**: `80` (punto de entrada público)
- **Config**: `services/Proxy/nginx.container.conf`
- **Depende de**: api, webclient, rosbridge

El proxy reemplaza al nginx instalado en el host. Rutea tráfico a los demás servicios por hostname:

| Path | Destino | Tipo |
|------|---------|------|
| `/` | `webclient:80` | HTTP (proxy a la SPA) |
| `/api/*` | `api:8000` | HTTP (quita prefijo `/api`) |
| `/ws/*` | `api:8000` | WebSocket (quita prefijo `/ws`) |
| `/m2m/*` | `api:8000` | HTTP (solo intranet) |
| `/rosbridge/` | `rosbridge:9090` | WebSocket (solo intranet) |

---

## Red y Comunicación

Todos los contenedores están en la red `labs-remoto` y se resuelven por nombre DNS:

```
proxy ──► api:8000
proxy ──► webclient:80
proxy ──► rosbridge:9090
api   ──► db:5432
api   ──► rosbridge:9090 (WebSocket)
```

Los puertos publicados al host son mínimos:

| Servicio | Puerto en host | Motivo |
|----------|---------------|--------|
| proxy | `0.0.0.0:80` | Punto de entrada público |
| db | `127.0.0.1:5432` | Migraciones con dbmate desde localhost |
| rosbridge | `127.0.0.1:9090` | Acceso local para debugging |
| api | — | Solo accesible via proxy |
| webclient | — | Solo accesible via proxy |

---

## Cadena de Dependencias

```
db ─────────┐
             ├──► api ──────┐
rosbridge ──┘               ├──► proxy
webclient ──────────────────┘
```

systemd respeta estas dependencias automáticamente. Al ejecutar `systemctl start proxy`, arranca primero db y rosbridge, luego api y webclient, y finalmente proxy.

Las dependencias se declaran en los archivos `.container` con las directivas:
- `Requires=` — el servicio no puede arrancar sin sus dependencias
- `After=` — espera a que las dependencias arranquen antes de iniciar

---

## Variables de Entorno

Los archivos `.env` se configuran manualmente en el servidor en `/etc/containers/env/`:

**`/etc/containers/env/db.env`**:
```env
POSTGRES_PASSWORD=<contraseña>
POSTGRES_USER=<usuario>
POSTGRES_DB=ciie_db
```

**`/etc/containers/env/api.env`**:
```env
POSTGRES_PASSWORD=<contraseña>
POSTGRES_USER=<usuario>
POSTGRES_DB=ciie_db
POSTGRES_URL=db:5432
ROSBRIDGE_URL=ws://rosbridge:9090
JWT_SECRET_KEY=<clave_secreta>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Notar que `POSTGRES_URL` y `ROSBRIDGE_URL` usan los hostnames de los contenedores (`db`, `rosbridge`), no `localhost`.

---

## Proceso de Deploy

### Setup inicial del servidor

Solo se hace una vez:

```bash
# 1. Instalar Podman
sudo apt install podman

# 2. Crear directorio de env vars
sudo mkdir -p /etc/containers/env
# Crear db.env y api.env con los valores de producción

# 3. Copiar los quadlets
sudo cp quadlets/*.container quadlets/*.network quadlets/*.volume \
    /etc/containers/systemd/

# 4. Recargar systemd
sudo systemctl daemon-reload
```

### Deploy con el script

Desde la máquina local del desarrollador:

```bash
./quadlets/deploy.sh usuario@servidor
```

### Flujo completo

Cuando se ejecuta `deploy.sh` sin flags, el flujo es:

```
 LOCAL                                          SERVIDOR
 ─────                                          ────────
 1. podman build
    services/Api/Dockerfile         → localhost/labs-remoto/api
    services/WebClient/Dockerfile   → localhost/labs-remoto/webclient
    services/RosBridge/Dockerfile   → localhost/labs-remoto/rosbridge
    services/Proxy/Dockerfile       → localhost/labs-remoto/proxy

 2. podman save
    Exporta cada imagen a quadlets/.build-cache/<servicio>.tar

 3. scp
    Transfiere los .tar ──────────────────────► /tmp/<servicio>.tar

 4. ssh + podman load     ◄─────────────────── Carga las imágenes

 5. ssh + systemctl       ◄─────────────────── Reinicia los servicios
    restart db rosbridge api webclient proxy

 6. Limpieza local
    Elimina quadlets/.build-cache/
```

### Flujo parcial

El script permite ejecutar solo una parte del flujo:

- **Solo build** (`-b`): pasos 1-2. Útil para compilar y verificar que las imágenes se crean correctamente antes de desplegar
- **Solo deploy** (`-d`): pasos 2-5. Requiere haber ejecutado `-b` previamente. Útil si el build ya se hizo y solo se quiere transferir
- **Deploy sin reload** (`-d --no-reload`): pasos 2-4. Carga las imágenes pero no reinicia los servicios

---

## El Script deploy.sh

### Sintaxis

```
./deploy.sh <servidor> [-c <servicio>]... [[-b|--build-only]|[[-d|--deploy-only] [--no-reload]]]
```

### Modos de operación

| Flags | Qué hace |
|-------|----------|
| *(ninguno)* | Flujo completo: build → export → transfer → load → restart |
| `-b` / `--build-only` | Solo compila y exporta localmente |
| `-d` / `--deploy-only` | Solo exporta, transfiere, carga y reinicia |
| `-d --no-reload` | Como `-d` pero sin reiniciar servicios |

### Ejemplos

```bash
# Deploy completo de todos los servicios
./quadlets/deploy.sh admin@192.168.1.100

# Solo compilar api y proxy localmente
./quadlets/deploy.sh admin@192.168.1.100 -c api -c proxy -b

# Desplegar imágenes ya compiladas, sin reiniciar
./quadlets/deploy.sh admin@192.168.1.100 -c api -c proxy -d --no-reload

# Compilar y desplegar solo rosbridge
./quadlets/deploy.sh admin@192.168.1.100 -c rosbridge
```

---

## Operaciones Comunes

```bash
# Ver estado de todos los servicios
sudo systemctl status db api rosbridge webclient proxy

# Seguir logs de un servicio en tiempo real
sudo journalctl -u api -f

# Reiniciar un servicio individual
sudo systemctl restart api

# Detener todo
sudo systemctl stop proxy api webclient rosbridge db

# Ver logs combinados de todos los servicios
sudo journalctl -u db -u api -u rosbridge -u webclient -u proxy -f

# Ejecutar migraciones de base de datos
cd services/Db
DATABASE_URL="postgres://<usuario>:<contraseña>@127.0.0.1:5432/ciie_db?sslmode=disable" \
    dbmate up
```

---

## Diferencias con el Proxy en Host

La documentación en [`red_y_despliegue.md`](./red_y_despliegue.md) describe la arquitectura original donde nginx está instalado directamente en el host. En la configuración de producción con quadlets, nginx se containerizó:

| Aspecto | Antes (host) | Ahora (contenedor) |
|---------|-------------|-------------------|
| **Instalación** | `apt install nginx` + `systemctl` | Imagen `nginx:alpine` via quadlet |
| **Config** | `services/Proxy/nginx.conf` | `services/Proxy/nginx.container.conf` |
| **TLS** | certbot + Let's Encrypt | No (por ahora) |
| **SPA** | Archivos estáticos en `/var/www/labs-remoto/` | `proxy_pass http://webclient:80` |
| **Upstreams** | `127.0.0.1:8000`, `127.0.0.1:9090` | `api:8000`, `rosbridge:9090` |
| **Restricción intranet** | `allow`/`deny` por IP | Misma lógica, verificar con red de Podman |

La topología de red y las decisiones documentadas en `red_y_despliegue.md` siguen siendo válidas — lo que cambió es la implementación del proxy, no el diseño.
