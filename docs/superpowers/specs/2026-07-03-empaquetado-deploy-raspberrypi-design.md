# Diseño: empaquetado y deploy del controller de la RaspberryPi

- **Fecha**: 2026-07-03
- **Servicio**: `services/RaspberryPi/`
- **Estado**: aprobado, pendiente de plan de implementación

## Problema

El controller (`services/RaspberryPi/`) está pineado a Python `>=3.13.7` y el ambiente de
deploy es una Raspberry Pi con Raspbian que trae Python 3.11. No existe hoy ningún mecanismo
de empaquetado para la Pi: `quadlets/deploy.sh` solo cubre los servicios del servidor central
(api, webclient, proxy, db), no la Pi.

### Reencuadre del problema (importante)

El planteo inicial ("3.11 vs 3.13") **se disuelve** al containerizar, pero aparece otra
restricción real:

- En la Pi de deploy el controller corre con `LOCAL_STRATEGY=Ros2Strategy`. ROS 2 **no** se
  instala nativamente en Raspbian; los demás sistemas ROS 2 de la Pi ya corren sobre Docker.
  Por eso el controller también se containeriza.
- Si el contenedor debe traer ROS 2 (para `rclpy`), la base natural es `ros:jazzy` =
  Ubuntu 24.04 = **Python 3.12**. No hay distro de ROS 2 sobre Python 3.13 hoy
  (Rolling/Kilted siguen en 3.12).
- Conclusión: **el target real no es 3.11 ni 3.13, es 3.12.** El Python 3.11 del host
  Raspbian deja de importar porque el contenedor trae su propio intérprete.

### Bloqueo de código a resolver

El código usa **PEP 696 (defaults de type-param, solo 3.13)** en dos lugares, que romperían
al importar `type_defs.py` dentro de Jazzy (3.12) con `SyntaxError` en tiempo de parseo:

- `controller/type_defs.py:18` → `class JsonRpcRequest[T = Any](TypedDict)`
- `controller/type_defs.py:24` → `class JsonRpcResponse[T = Any](TypedDict)`

Todo el resto de la sintaxis moderna que usa el código ya es válida en 3.12: `type StatusData`
(PEP 695), genéricos `[T]` sin default, `typing.override`, `typing.Self`.

> Nota: este mismo bloqueo es un **bug latente actual** en `Dockerfile.ros` (dev), que dice
> correr "sin cambios de código" en Jazzy/3.12 pero fallaría al importar `type_defs.py`.
> El fix de este spec lo resuelve de paso.

## Objetivo

Empaquetar el controller como una imagen Docker self-contained (con ROS 2 + Python 3.12),
entregarla a la Pi por SSH, y correrla como contenedor de larga vida gestionado por Docker
Compose, con la CLI de `services/RaspberryPi/cli/` como interfaz de control operativo.

## Decisiones tomadas

1. **Target Python 3.12** (impuesto por ROS 2 Jazzy). Se baja `requires-python` a `>=3.12`
   y se quitan los defaults PEP 696. Dev sigue usando 3.13 vía uv sin problema (3.12 es piso,
   no techo).
2. **Docker en la Pi** (no Podman/quadlets). El servidor central usa Podman/quadlets; la Pi
   usa Docker como sus otros contenedores ROS. Divergencia intencional: meter Podman en una
   Pi que ya es Docker introduce fricción Podman↔Docker (redes, `/dev/shm` para DDS entre
   runtimes) que no paga por sí sola.
3. **Sin systemd unit.** El ciclo de vida lo cubre la restart policy de Docker
   (`restart: unless-stopped` → boot vía el daemon de Docker + auto-restart en crash). El
   ordering respecto al agente ROS es innecesario: el controller ya tiene discovery DDS +
   reconexión WS con backoff, así que tolera que el agente arranque después.
   - **Convención que se establece para la Pi**: cada servicio = un servicio en `compose.yaml`
     con `restart: unless-stopped`; infra vía `docker compose up -d`/`down`; app vía `robot-cli`.
   - **Criterio de desvío a systemd** (documentado para quien herede): solo si aparece
     orquestación cross-servicio que Docker no exprese (ordering duro con health-gating, árbol
     de dependencias real entre daemons). Dado el reconnect del controller, probablemente nunca.
4. **Sin passthrough de serial.** Con `Ros2Strategy` el Arduino lo maneja el *otro* contenedor
   ROS (el scraper); el nuestro habla por topics DDS. No se pasa `/dev/ttyUSB` al contenedor.
5. **Build/entrega: cross-build + save/load por SSH.** Espejo del patrón de
   `quadlets/deploy.sh`: build ARM en la máquina de dev, `docker save | ssh | docker load`,
   `docker compose up -d` remoto.
6. **CLI vía `docker exec`.** El host Raspbian es 3.11 y `cli/` usa sintaxis 3.12; la CLI
   corre dentro del contenedor. Un wrapper `robot-cli` en el host hace
   `docker exec -it labs-remoto-robot python -m cli "$@"`. El Unix socket queda dentro del
   contenedor (no se monta); no se instala Python en el host.

## Diseño

### 1. Compatibilidad Python 3.12 (cambio de código)

- `controller/type_defs.py:18`: `class JsonRpcRequest[T = Any](TypedDict)` →
  `class JsonRpcRequest[T](TypedDict)`.
- `controller/type_defs.py:24`: `class JsonRpcResponse[T = Any](TypedDict)` →
  `class JsonRpcResponse[T](TypedDict)`.
- `pyproject.toml`: `requires-python = ">=3.13.7"` → `requires-python = ">=3.12"`.

Impacto funcional: **cero**. Los usos son o bien `JsonRpcResponse[StatusData]` (parámetro
explícito) o `JsonRpcResponse` pelado; el default solo afectaba type-checking de la forma
pelada, y en runtime los genéricos de TypedDict se borran.

### 2. Imagen de deploy — `services/RaspberryPi/Dockerfile`

Imagen **self-contained** (código copiado, no montado como volumen), separada del
`Dockerfile.ros` de dev:

- `FROM docker.io/library/ros:jazzy` (multi-arch: incluye arm64).
- venv `/opt/venv --system-site-packages` (para ver `rclpy`/`std_msgs` del entorno ROS),
  mismas deps que `pyproject.toml` (pydantic, pydantic-settings, python-dotenv, requests,
  pyserial, websockets). Sin `pytest` en la imagen de deploy.
- `COPY controller/ cli/ pyproject.toml` dentro de la imagen.
- Hornea `ENV ROS_DOMAIN_ID=42` y `ENV FASTDDS_BUILTIN_TRANSPORTS=UDPv4` (igual que
  `Dockerfile.ros`, para discovery DDS entre contenedores).
- Hereda el `ENTRYPOINT /ros_entrypoint.sh` de la imagen ROS (sourcea `setup.bash`).
- `CMD ["python", "-m", "controller"]`. La strategy se elige por entorno
  (`LOCAL_STRATEGY=Ros2Strategy`), no se hornea.

`Dockerfile.ros` (dev, código montado como volumen) se mantiene para iterar localmente.

> Deuda opcional (fuera de alcance): factorizar una base común entre `Dockerfile` y
> `Dockerfile.ros` para no duplicar la instalación de deps. No se hace ahora para no arrastrar
> scope; se anota.

### 3. Runtime en la Pi — `services/RaspberryPi/compose.yaml`

Un servicio `controller`:

- `image:` apuntando al tag pre-cargado (p. ej. `labs-remoto/controller:jazzy` — sin prefijo
  `localhost/`, que es namespace de Podman; en Docker el tag va plano),
  **sin `build:`** — la imagen llega por `docker load`, no se compila en la Pi.
- `network_mode: host` — discovery DDS con el contenedor del agente ROS y acceso a la API.
- `restart: unless-stopped`.
- `env_file: .env` (config de la Pi: `SERVER_URL`, `LOCAL_STRATEGY=Ros2Strategy`,
  `REMOTE_STRATEGY=WsStrategy`, `MOCK_ROBOT=0`, `ROS2_DOMAIN_ID=42`, topics, etc.).
- **Bind-mount** de `robot-metadata.json` (la identidad del robot debe sobrevivir reinicios;
  no se hornea en la imagen).

Ciclo de vida: `docker compose up -d` / `docker compose down`. Boot y crash los cubre Docker.

### 4. CLI de control — wrapper `robot-cli`

Script en el host que delega al contenedor:

```sh
#!/usr/bin/env sh
exec docker exec -it labs-remoto-robot python -m cli "$@"
```

El Unix socket de gestión (`SOCKET_PATH`, default `/tmp/robot-controller.sock`) queda dentro
del contenedor; la CLI corre en el mismo contenedor y lo alcanza directo. No se monta el
socket ni se instala Python en el host.

### 5. Build y entrega — targets de Makefile en `services/RaspberryPi/`

Espejo del patrón de `quadlets/deploy.sh`:

- `deploy.build`: `docker buildx build --platform linux/arm64 -t <img>:jazzy -f Dockerfile .`
  → `docker save <img>:jazzy -o <tar>`.
- `deploy.push`: `docker save <img> | ssh <pi> 'docker load'` + `scp` de `compose.yaml`,
  `.env` (o `.env.example`) y `robot-cli` a la Pi.
- `deploy.up`: `ssh <pi> 'cd <dir> && docker compose up -d'`.
- (host/dir/tag configurables por variables del Makefile o `.env` de deploy.)

Las deps con extensión nativa (p. ej. `pydantic-core`) tienen wheels arm64 en PyPI, así que
el build bajo qemu **no compila**, solo baja wheels. Lento pero robusto.

### 6. Verificación

- Build arm64 con `docker buildx` + `docker run` de la imagen (bajo qemu en dev):
  `python -c "import rclpy, controller"` debe importar limpio en 3.12 (valida el fix PEP 696
  y que `rclpy` está visible).
- `make ros.test` (contenedor con rclpy real) sigue verde tras el cambio de `type_defs.py`.
- Smoke local en dev con uv 3.13 (`uv run -m controller` en modo mock) sigue arrancando
  (confirma que bajar el pin no rompe dev).

## Supuestos / prerrequisitos

1. **La Pi de deploy es arm64 (64-bit).** Las imágenes de ROS 2 Jazzy solo existen para
   amd64/arm64, **no armv7/armhf**. Que ya corran contenedores ROS 2 en esa Pi *confirma* que
   es arm64; se deja como prerequisito a validar antes del primer deploy.
2. **`SERVER_URL`** (dónde vive la API respecto a la Pi) es config del `.env`, no parte del
   diseño de empaquetado.
3. **No se tocan los quadlets.** La Pi está fuera del pipeline `quadlets/deploy.sh` (que cubre
   solo el servidor central). El nuevo `Dockerfile` de la Pi no tiene quadlet asociado.

## Fuera de alcance

- Factorizar base común entre `Dockerfile` y `Dockerfile.ros` (deuda anotada).
- Registry / pull en la Pi (se eligió save/load por SSH; migrar a registry queda para cuando
  haya N Pis).
- systemd units (criterio de reconsideración documentado en la decisión 3).
- Passthrough de serial (no aplica con `Ros2Strategy`).
