# Empaquetado y Deploy del Controller de la RaspberryPi — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empaquetar el controller de `services/RaspberryPi/` como una imagen Docker self-contained (ROS 2 Jazzy + Python 3.12) y entregarla a la Pi por SSH, corriéndola como contenedor de larga vida vía Docker Compose, con la CLI accesible por `docker exec`.

**Architecture:** El controller se pinea hoy a Python 3.13 (usa PEP 696), pero el target de deploy es un contenedor `ros:jazzy` (Python 3.12, porque ahí vive `rclpy` para `Ros2Strategy`). Se baja el código a 3.12 (cambio trivial), se construye una imagen que COPIA el código, se corre con `docker compose` + `restart: unless-stopped` (sin systemd), y la CLI corre dentro del contenedor vía un wrapper `robot-cli`. Build con Podman en la dev box (docker no está instalado), entrega vía `podman save --format docker-archive | ssh | docker load`.

**Tech Stack:** Python 3.12, ROS 2 Jazzy (`ros:jazzy`), Podman (dev build) / Docker (Pi runtime), Docker Compose, pydantic-settings, Makefile.

**Spec:** `docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`

## Global Constraints

- **Target Python 3.12**: `requires-python = ">=3.12"`. Prohibido introducir sintaxis 3.13-only (PEP 696 defaults de type-param `[T = X]`). 3.12 es piso, no techo (dev sigue en 3.13 vía uv).
- **Tag de imagen**: `localhost/labs-remoto/controller:jazzy` — verbatim, en todos lados. El prefijo `localhost/` lo pone Podman y se preserva a través de `save`→`docker load`; el `image:` del compose debe machearlo exacto.
- **Build en dev = Podman** (docker NO está instalado en la dev box). Runtime en la Pi = Docker.
- **Sin passthrough de serial**: con `Ros2Strategy` el Arduino lo maneja otro contenedor ROS. No se pasa `/dev/ttyUSB`.
- **Sin systemd unit**: ciclo de vida vía `restart: unless-stopped` de Docker.
- **`network_mode: host`** en el contenedor (discovery DDS + acceso a la API).
- **Env horneado en la imagen**: `ROS_DOMAIN_ID=42`, `FASTDDS_BUILTIN_TRANSPORTS=UDPv4`.
- **`container_name: labs-remoto-robot`** fijo (para `docker exec` determinístico).
- **No tocar `quadlets/`**: la Pi está fuera de ese pipeline (que cubre solo el servidor central).
- **Idioma**: comentarios y docs en español (convención del repo).

---

### Task 1: Compatibilidad Python 3.12 (fix PEP 696)

Elimina los defaults de type-param (PEP 696, solo 3.13) que romperían al importar bajo Jazzy (3.12) con `SyntaxError` en parseo. Baja `requires-python`.

**Files:**
- Modify: `services/RaspberryPi/controller/type_defs.py:18,24`
- Modify: `services/RaspberryPi/pyproject.toml:6`

**Interfaces:**
- Consumes: nada.
- Produces: `type_defs.py` compilable en 3.12; `JsonRpcRequest[T]` y `JsonRpcResponse[T]` siguen siendo genéricos parametrizables (misma API, sin el default `Any`).

- [ ] **Step 1: Escribir el chequeo que falla (py_compile bajo 3.12)**

`type_defs.py` solo importa de `typing` (sin deps externas), así que se compila con un Python 3.12 limpio que uv descarga on-the-fly.

Run:
```bash
cd services/RaspberryPi
uv run --python 3.12 --no-project python -m py_compile controller/type_defs.py
```
Expected: **FAIL** con `SyntaxError` en la línea 18 (`class JsonRpcRequest[T = Any]`) — los defaults de type-param no existen en 3.12.

- [ ] **Step 2: Aplicar el fix en `type_defs.py`**

Quitar ` = Any` de los dos type-params:

```python
class JsonRpcRequest[T](TypedDict):
    jsonrpc: str
    method: str
    params: NotRequired[T]
    id: Any

class JsonRpcResponse[T](TypedDict):
    jsonrpc: str
    result: T
    error: NotRequired[dict[str, Any]]
    id: Any
```

- [ ] **Step 3: Verificar que ahora compila en 3.12**

Run:
```bash
uv run --python 3.12 --no-project python -m py_compile controller/type_defs.py && echo "3.12 OK"
```
Expected: **PASS**, imprime `3.12 OK`.

- [ ] **Step 4: Bajar `requires-python` en `pyproject.toml`**

Cambiar la línea 6:
```toml
requires-python = ">=3.12"
```

- [ ] **Step 5: Confirmar que dev (3.13) sigue intacto**

Run:
```bash
uv sync && uv run pytest
```
Expected: **PASS** — la suite existente sigue verde en 3.13 (bajar el piso no rompe nada).

- [ ] **Step 6: Commit**

```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
git add services/RaspberryPi/controller/type_defs.py services/RaspberryPi/pyproject.toml
git commit -m "raspi: compatibilidad Python 3.12 (quitar defaults PEP 696) para deploy en Jazzy"
```

---

### Task 2: Dockerfile de deploy self-contained

Imagen que COPIA el código (artefacto portable), a diferencia de `Dockerfile.ros` (dev, volumen). Base `ros:jazzy` para `rclpy`. Valida el fix de Task 1 bajo 3.12 real.

**Files:**
- Create: `services/RaspberryPi/Dockerfile`

**Interfaces:**
- Consumes: código 3.12-compatible de Task 1.
- Produces: imagen `localhost/labs-remoto/controller:jazzy` con `WORKDIR /app`, código en `/app/controller` y `/app/cli`, venv en `/opt/venv` (en PATH), `CMD python -m controller`.

- [ ] **Step 1: Crear `services/RaspberryPi/Dockerfile`**

```dockerfile
# Imagen de DEPLOY self-contained del controller (Ros2Strategy, rclpy real).
# ROS 2 Jazzy = Ubuntu 24.04 = Python 3.12 (ver spec 2026-07-03-empaquetado-deploy-raspberrypi).
# A diferencia de Dockerfile.ros (dev, código montado como volumen), esta COPIA el código:
# artefacto portable que se transfiere a la Pi vía `docker load`.
FROM docker.io/library/ros:jazzy

# Deps del controller (mismas que pyproject.toml, SIN pytest) en un venv con
# --system-site-packages para ver rclpy/std_msgs del Python del sistema (ROS).
# ros:jazzy no trae ensurepip → instalar python3-venv primero.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3-venv \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m venv /opt/venv --system-site-packages \
 && /opt/venv/bin/pip install --no-cache-dir \
        "pydantic>=2.11.10" \
        "pydantic-settings>=2.13.1" \
        "python-dotenv>=1.1.1" \
        "requests>=2.32.5" \
        "pyserial>=3.5" \
        "websockets>=15.0"

ENV PATH="/opt/venv/bin:${PATH}"
# Mismo dominio DDS que el agente ROS de la Pi (para descubrirse por DDS).
ENV ROS_DOMAIN_ID=42
# Forzar UDPv4 en Fast DDS: el agente ROS corre en OTRO contenedor con su propio /dev/shm,
# así que el transporte por memoria compartida (default same-host) no entrega datos entre
# contenedores aunque el descubrimiento (UDP multicast) sí cruce. UDPv4 lo resuelve.
ENV FASTDDS_BUILTIN_TRANSPORTS=UDPv4
WORKDIR /app

# Código del controller y la CLI (artefacto self-contained, no volumen).
COPY controller/ ./controller/
COPY cli/ ./cli/
COPY pyproject.toml ./

# El ENTRYPOINT /ros_entrypoint.sh (heredado de ros:jazzy) sourcea /opt/ros/jazzy/setup.bash
# y ejecuta el CMD, dejando rclpy importable.
CMD ["python", "-m", "controller"]
```

- [ ] **Step 2: Build nativo (x86_64) con Podman**

Run:
```bash
cd services/RaspberryPi
podman build -t localhost/labs-remoto/controller:jazzy -f Dockerfile .
```
Expected: build exitoso, termina con `Successfully tagged localhost/labs-remoto/controller:jazzy` (o el hash de la imagen).

- [ ] **Step 3: Verificar imports bajo 3.12 real (valida Task 1 + rclpy visible)**

Run:
```bash
podman run --rm localhost/labs-remoto/controller:jazzy \
  sh -c "python -m compileall -q controller cli && python -c 'import rclpy; from controller import type_defs; print(\"import OK\")'"
```
Expected: imprime `import OK`. `compileall` byte-compila TODO el código bajo 3.12 (atrapa cualquier sintaxis 3.13 residual); el import confirma que `rclpy` está visible en el venv.

- [ ] **Step 4: Commit**

```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
git add services/RaspberryPi/Dockerfile
git commit -m "raspi: Dockerfile de deploy self-contained (ros:jazzy + controller)"
```

---

### Task 3: Runtime — compose.yaml, .env.deploy.example y robot-cli

Define cómo corre el contenedor en la Pi y cómo se controla. `.env` y `robot-metadata.json` están gitignoreados → se commitea un `.env.deploy.example` de plantilla; la metadata persiste vía un dir `data/` montado (evita la trampa del bind-mount a un archivo inexistente).

**Files:**
- Create: `services/RaspberryPi/compose.yaml`
- Create: `services/RaspberryPi/.env.deploy.example`
- Create: `services/RaspberryPi/robot-cli`

**Interfaces:**
- Consumes: imagen `localhost/labs-remoto/controller:jazzy` (Task 2); config vars de `controller/config.py` (`server_url`, `arduino_port`, `local_strategy`, `remote_strategy`, `metadata_file`, `mock_robot`, `create_default_metadata`, `ros2_*`).
- Produces: contenedor `labs-remoto-robot`; interfaz de control `robot-cli` (usa `${CONTAINER_ENGINE:-docker} exec -it labs-remoto-robot python -m cli`).

- [ ] **Step 1: Crear `services/RaspberryPi/compose.yaml`**

```yaml
# Runtime del controller en la Pi (Docker). Ver
# docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md
#
# La imagen llega por `docker load` (make deploy.push); NO se compila acá (sin `build:`).
# Ciclo de vida por restart policy de Docker (sin systemd). Control de app: ./robot-cli
services:
  controller:
    image: localhost/labs-remoto/controller:jazzy
    container_name: labs-remoto-robot
    # network host: discovery DDS con el contenedor del agente ROS (ROS_DOMAIN_ID=42) +
    # acceso a la API. Los ENV de DDS (ROS_DOMAIN_ID, FASTDDS_BUILTIN_TRANSPORTS) van horneados.
    network_mode: host
    restart: unless-stopped
    env_file: .env
    volumes:
      # La identidad del robot (robot-metadata.json) persiste entre reinicios.
      # Se monta el DIR (no el archivo) para que CREATE_DEFAULT_METADATA lo genere sin
      # que Docker cree un directorio espurio si el archivo aún no existe.
      # METADATA_FILE en .env debe apuntar a /app/data/robot-metadata.json.
      - ./data:/app/data
```

- [ ] **Step 2: Crear `services/RaspberryPi/.env.deploy.example`**

```bash
# Plantilla de config de DEPLOY del controller en la Pi (Ros2Strategy).
# Copiar a `.env` en la Pi y ajustar SERVER_URL. `.env` está gitignoreado.
SERVER_URL='http://CAMBIAME-API-HOST:8000/m2m/robot/'
# Requerido por config.py aunque Ros2Strategy no use serial (el Arduino lo maneja el agente ROS).
ARDUINO_PORT='/dev/null'
LOCAL_STRATEGY='Ros2Strategy'
REMOTE_STRATEGY='WsStrategy'
MOCK_ROBOT=0
# Idempotente: genera robot-metadata.json si no existe (persiste vía el mount ./data). Dejar en 1.
CREATE_DEFAULT_METADATA=1
METADATA_FILE='/app/data/robot-metadata.json'
ROS2_NODE_NAME='labs_remoto_robot'
ROS2_COMMAND_TOPIC='/inorbit/custom_command'
ROS2_DATA_TOPIC='/inorbit/custom_data'
# Debe coincidir con el ROS_DOMAIN_ID del agente ROS de la Pi (el scraper corre en 42).
ROS2_DOMAIN_ID=42
```

- [ ] **Step 3: Crear `services/RaspberryPi/robot-cli` (wrapper de la CLI)**

```sh
#!/usr/bin/env sh
# CLI de gestión del controller. Corre `python -m cli` DENTRO del contenedor: el host
# Raspbian tiene Python 3.11 y la CLI usa sintaxis 3.12, así que no puede correr nativa.
# Ver docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md
#
# CONTAINER_ENGINE=docker por default (Pi). Override a `podman` para testear en la dev box:
#   CONTAINER_ENGINE=podman ./robot-cli status
exec "${CONTAINER_ENGINE:-docker}" exec -it labs-remoto-robot python -m cli "$@"
```

- [ ] **Step 4: Hacer `robot-cli` ejecutable**

Run:
```bash
cd services/RaspberryPi && chmod +x robot-cli && test -x robot-cli && echo "exec OK"
```
Expected: imprime `exec OK`.

- [ ] **Step 5: Smoke del contenedor + camino de la CLI (con MockStrategy, sin ROS)**

Se usa `MockStrategy` a propósito: valida el empaquetado (boot del core + socket de gestión + CLI vía exec) **sin** depender de un agente ROS ni de la API. El deploy real usa `Ros2Strategy` vía `.env`.

Run:
```bash
cd services/RaspberryPi
podman run -d --name labs-remoto-robot \
  -e SERVER_URL=http://localhost:8000/m2m/robot/ \
  -e ARDUINO_PORT=/dev/null \
  -e LOCAL_STRATEGY=MockStrategy \
  -e REMOTE_STRATEGY=WsStrategy \
  -e MOCK_ROBOT=1 \
  -e CREATE_DEFAULT_METADATA=1 \
  localhost/labs-remoto/controller:jazzy
sleep 4
podman exec -i labs-remoto-robot python -m cli status
echo "--- exit: $? ---"
podman rm -f labs-remoto-robot
```
Expected: `python -m cli status` imprime el status del core (JSON con `core`/`local`/`remote`) y sale 0. El contenedor sigue vivo pese a que la API en `localhost:8000` no responde (WsStrategy reintenta con backoff, no crashea). Esto prueba: boot del controller en 3.12, socket de gestión levantado, y el camino `exec → python -m cli` que `robot-cli` usa.

- [ ] **Step 6: Ignorar `data/` local (no versionar credenciales generadas en smokes/dev)**

Agregar a `services/RaspberryPi/.gitignore`:
```
data/
```

- [ ] **Step 7: Commit**

```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
git add services/RaspberryPi/compose.yaml services/RaspberryPi/.env.deploy.example services/RaspberryPi/robot-cli services/RaspberryPi/.gitignore
git commit -m "raspi: compose + .env.deploy.example + wrapper robot-cli para deploy"
```

---

### Task 4: Targets de Makefile para build y entrega

Automatiza cross-build arm64 (Podman) + entrega por SSH (`docker load`) + arranque remoto. Espejo del patrón de `quadlets/deploy.sh`.

**Files:**
- Modify: `services/RaspberryPi/Makefile` (append)

**Interfaces:**
- Consumes: `Dockerfile` (Task 2), `compose.yaml`/`robot-cli`/`.env.deploy.example` (Task 3).
- Produces: targets `deploy.build`, `deploy.push`, `deploy.up`, `deploy.restart`, `deploy`.

- [ ] **Step 1: Agregar los targets de deploy al final del `Makefile`**

Append a `services/RaspberryPi/Makefile`:

```makefile

# --- Deploy a la Pi (Docker) --------------------------------------------------
# Build con PODMAN en dev (docker no está instalado en dev), save como docker-archive
# (tar que `docker load` acepta en la Pi), load por SSH. Cross-build arm64 requiere
# binfmt qemu registrado en el host (paquete qemu-user-static).
DEPLOY_IMAGE := localhost/labs-remoto/controller:jazzy
DEPLOY_TAR := /tmp/labs-remoto-controller-arm64.tar
PI_HOST ?= pi@raspberrypi.local
PI_DIR ?= labs-remoto-controller

.PHONY: deploy.build deploy.push deploy.up deploy.restart deploy
deploy.build:
	podman build --platform linux/arm64 -t $(DEPLOY_IMAGE) -f Dockerfile .
	podman save --format docker-archive -o $(DEPLOY_TAR) $(DEPLOY_IMAGE)

deploy.push:
	cat $(DEPLOY_TAR) | ssh $(PI_HOST) 'docker load'
	ssh $(PI_HOST) 'mkdir -p $(PI_DIR)/data'
	scp compose.yaml robot-cli .env.deploy.example $(PI_HOST):$(PI_DIR)/

deploy.up:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d'

deploy.restart:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d --force-recreate'

deploy: deploy.build deploy.push deploy.up
```

- [ ] **Step 2: Verificar que el Makefile parsea y los targets existen**

Run:
```bash
cd services/RaspberryPi
make -n deploy.build deploy.push deploy.up deploy.restart
```
Expected: imprime los comandos de cada target (dry-run, `-n`) sin error de sintaxis del Makefile. Confirma que las variables se expanden y los targets están declarados.

- [ ] **Step 3: (Opcional, si hay binfmt qemu) Verificar cross-build arm64**

Prerequisito: `qemu-user-static` registrado. Si no está disponible, saltar este step y anotarlo — el build arm64 se validará en el primer deploy real.

Run:
```bash
cd services/RaspberryPi
make deploy.build
podman image inspect localhost/labs-remoto/controller:jazzy --format '{{.Architecture}}'
```
Expected: `make deploy.build` completa y `podman image inspect … --format '{{.Architecture}}'` imprime `arm64`. Nota: si el host no tiene binfmt qemu, `podman build --platform linux/arm64` falla al ejecutar comandos arm64 (apt/pip) — ahí instalar `qemu-user-static` o diferir al deploy real.

- [ ] **Step 4: Commit**

```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
git add services/RaspberryPi/Makefile
git commit -m "raspi: targets de Makefile para cross-build y deploy a la Pi"
```

---

### Task 5: Documentación del flujo de deploy

Documenta el empaquetado, el runtime en la Pi y `robot-cli` en la guía del servicio y el README. Cierra la brecha de que hoy no hay mecanismo documentado para la Pi.

**Files:**
- Modify: `services/RaspberryPi/CLAUDE.md` (sección de ejecución)
- Modify: `services/RaspberryPi/README.md` y `README.es.md` (nota + link)

**Interfaces:**
- Consumes: todo lo anterior (Dockerfile, compose, robot-cli, targets de Makefile).
- Produces: docs. No hay artefacto de código.

- [ ] **Step 1: Agregar sección de deploy a `services/RaspberryPi/CLAUDE.md`**

Insertar tras la sección "### Correr Ros2Strategy con Podman (ROS 2 Jazzy)":

```markdown
### Deploy en la Pi (Docker Compose)

El controller se empaqueta como imagen Docker self-contained (ROS 2 Jazzy → **Python 3.12**;
ver `docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`). El Python
3.11 del host Raspbian no se usa: el contenedor trae su propio intérprete.

- **Artefacto**: `services/RaspberryPi/Dockerfile` (copia el código; distinto de `Dockerfile.ros`
  que monta volumen para dev).
- **Runtime**: `compose.yaml` — un servicio `controller`, `network_mode: host`,
  `restart: unless-stopped`, `container_name: labs-remoto-robot`. Sin systemd: el ciclo de vida
  lo cubre la restart policy de Docker. Sin passthrough de serial (el Arduino lo maneja el agente ROS).
- **Config**: copiar `.env.deploy.example` → `.env` en la Pi y ajustar `SERVER_URL`. La identidad
  del robot persiste en `./data/` (montado).
- **Control**: `./robot-cli <comando>` corre la CLI dentro del contenedor vía `docker exec`
  (el host es 3.11, la CLI usa 3.12). En dev: `CONTAINER_ENGINE=podman ./robot-cli status`.

Build y entrega (Podman en dev — docker no está en dev — → `docker load` en la Pi):

    make deploy.build      # cross-build arm64 + save (docker-archive). Requiere binfmt qemu.
    make deploy.push       # docker load por SSH + scp de compose/robot-cli/.env.example
    make deploy.up         # docker compose up -d en la Pi
    make deploy            # los tres encadenados
    # PI_HOST y PI_DIR son overridables: make deploy PI_HOST=usuario@ip

> La Pi usa **Docker** (como sus otros contenedores ROS), no Podman/quadlets. Divergencia
> intencional respecto al servidor central. La Pi está fuera de `quadlets/deploy.sh`.
```

- [ ] **Step 2: Agregar nota + link en `services/RaspberryPi/README.md`**

En la sección de ejecución/deploy del README (inglés), agregar:

```markdown
## Deployment (Raspberry Pi)

Packaged as a self-contained Docker image (ROS 2 Jazzy → Python 3.12) and run via Docker
Compose (`restart: unless-stopped`, no systemd). Build with Podman on the dev machine and ship
over SSH: `make deploy` (see `PI_HOST`/`PI_DIR` overrides). Manage the running controller with
`./robot-cli <command>` (runs the CLI inside the container via `docker exec`).

Design: [`docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`](../../docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md).
See the Spanish version: [README.es.md](README.es.md).
```

- [ ] **Step 3: Agregar la nota equivalente en español a `services/RaspberryPi/README.es.md`**

```markdown
## Despliegue (Raspberry Pi)

Se empaqueta como imagen Docker self-contained (ROS 2 Jazzy → Python 3.12) y corre vía Docker
Compose (`restart: unless-stopped`, sin systemd). Se construye con Podman en la máquina de dev
y se envía por SSH: `make deploy` (con overrides `PI_HOST`/`PI_DIR`). El controller en marcha se
gestiona con `./robot-cli <comando>` (corre la CLI dentro del contenedor vía `docker exec`).

Diseño: [`docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md`](../../docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md).
Ver versión en inglés: [README.md](README.md).
```

- [ ] **Step 4: Verificar que los links y archivos existen**

Run:
```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
test -f docs/superpowers/specs/2026-07-03-empaquetado-deploy-raspberrypi-design.md && echo "spec OK"
grep -q "Deploy en la Pi" services/RaspberryPi/CLAUDE.md && echo "CLAUDE.md OK"
grep -q "Deployment (Raspberry Pi)" services/RaspberryPi/README.md && echo "README OK"
grep -q "Despliegue (Raspberry Pi)" services/RaspberryPi/README.es.md && echo "README.es OK"
```
Expected: imprime las cuatro líneas `… OK`.

- [ ] **Step 5: Commit**

```bash
cd /home/phosph/personal-proyects/ciie/core/labs-remoto
git add services/RaspberryPi/CLAUDE.md services/RaspberryPi/README.md services/RaspberryPi/README.es.md
git commit -m "docs(raspi): documentar el flujo de deploy en la Pi (Docker Compose + robot-cli)"
```

---

## Verificación end-to-end (manual, requiere la Pi)

No automatizable en la dev box (necesita hardware/SSH). Documentar como checklist de primer deploy:

1. **Prerequisito**: confirmar que la Pi es **arm64** (`ssh <pi> uname -m` → `aarch64`). Que ya corran contenedores ROS 2 Jazzy lo implica, pero validar.
2. `make deploy PI_HOST=<usuario@pi>` → build arm64, load, up.
3. En la Pi: `cp .env.deploy.example .env` y ajustar `SERVER_URL` (si no se hizo antes de `deploy.up`).
4. `ssh <pi> 'docker ps'` → contenedor `labs-remoto-robot` en estado `Up`.
5. `ssh <pi> 'cd labs-remoto-controller && ./robot-cli status'` → status del core.
6. Verificar telemetría DDS: con el agente ROS corriendo, `robot-cli` debe reflejar conexión local activa (`Modo`/`Tension`/`Velocidad`).
7. Aprobar el robot en la API (`POST /admin/robot/{id}/approve`) y confirmar que el WS se establece.

---

## Notas de implementación

- **`sync-quadlets` NO aplica**: aunque este plan crea un `Dockerfile`, es para la Pi (Docker, fuera de `quadlets/`). No disparar esa skill; no hay quadlet asociado.
- **Deuda anotada (fuera de alcance)**: factorizar base común entre `Dockerfile` y `Dockerfile.ros` para no duplicar la instalación de deps.
- **Orden de tasks**: 1→2→3→4→5 es secuencial (cada una consume la anterior). Task 5 (docs) puede solaparse pero se deja al final para reflejar el estado real.
