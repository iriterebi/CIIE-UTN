# Compilar desde ../..
# ---- Stage: base --------------------------------------------------------------
FROM docker.io/library/ros:lyrical AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_PYTHON=/usr/bin/python3.14 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY services/PiSystemAgent/pyproject.toml ./services/PiSystemAgent/pyproject.toml

# Venv con acceso a /usr/lib/python3/dist-packages: ahí viven las deps apt de
# rclpy/rosidl (lark, empy, yaml...). Sin esto el venv no las ve.
RUN uv venv --system-site-packages /app/.venv
# `python` del venv en el PATH también en este stage: los targets `ros.*` del Makefile
# usan esta imagen (controller-dev) directamente, no el stage final.
ENV PATH="/app/.venv/bin:$PATH"

# Instalar dependencias sin el código fuente (cacheo de capas)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package ciie-remote-lab-native --no-dev --no-install-workspace

# Copiar código fuente de la Api
COPY services/PiSystemAgent/controller /app/services/PiSystemAgent/controller
COPY services/PiSystemAgent/cli /app/services/PiSystemAgent/cli

# Instalar el paquete del workspace
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package ciie-remote-lab-native --no-dev


# ---- Stage: final (runtime) ---------------------------------------------------
# Nombrado: `make deploy.build` lo pide con --target final. Un build sin --target
# (ej. el `build:` de compose.yaml) igual construye este stage, por ser el último.
FROM docker.io/library/ros:lyrical AS final

WORKDIR /app

COPY --from=base /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY services/PiSystemAgent/controller /app/services/PiSystemAgent/controller
COPY services/PiSystemAgent/cli /app/services/PiSystemAgent/cli


ENV ROS_DOMAIN_ID=42 \
    FASTDDS_BUILTIN_TRANSPORTS=UDPv4

# Defaults de deploy (Ros2Strategy). env_file/-e en runtime siempre gana sobre
# el ENV horneado acá (precedencia estándar de Docker), así que siguen siendo
# overrideables si hiciera falta.
#
# SERVER_URL y ARDUINO_PORT NO se hornean a propósito: Config los exige sin
# default (varían por deploy / ARDUINO_PORT es requerido igual aunque
# Ros2Strategy no lo use — bug de config.py fuera de alcance acá). Siguen
# viniendo de .env/-e siempre.
ENV LOCAL_STRATEGY=Ros2Strategy \
    REMOTE_STRATEGY=WsStrategy \
    MOCK_ROBOT=0 \
    CREATE_DEFAULT_METADATA=1 \
    METADATA_FILE=/app/data/robot-metadata.json \
    ROS2_NODE_NAME=labs_remoto_robot \
    ROS2_COMMAND_TOPIC=/inorbit/custom_command
# Mismo valor que ROS_DOMAIN_ID (stage base) pero es OTRA variable: esta es el
# campo de Config (app), aquella es el ENV de infra DDS del SO. No deduplicar.
ENV ROS2_DATA_TOPIC=/inorbit/custom_data \
    ROS2_DOMAIN_ID=42 \
    CAMERA_NODE_NAME=labs_remoto_camera \
    CAMERA_TOPIC=/usb_cam/image_raw \
    CAMERA_JPEG_QUALITY=80

CMD ["python", "-m", "services.PiSystemAgent.controller"]
