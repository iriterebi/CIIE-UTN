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
COPY services/PiRobotDriver/pyproject.toml ./services/PiRobotDriver/pyproject.toml

# Venv con acceso a /usr/lib/python3/dist-packages: ahí viven las deps apt de
# rclpy/rosidl (lark, empy, yaml...). Sin esto el venv no las ve.
RUN uv venv --system-site-packages /app/.venv

# Instalar dependencias sin el código fuente (cacheo de capas)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package ciie-remote-lab-robot-driver --no-dev --no-install-workspace

# Copiar código fuente de la Api
COPY services/PiRobotDriver/agent /app/services/PiRobotDriver/agent

# Instalar el paquete del workspace
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package ciie-remote-lab-robot-driver --no-dev


# ---- Stage: runtime -----------------------------------------------------------
FROM docker.io/library/ros:lyrical

WORKDIR /app

COPY --from=base /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ROS_DOMAIN_ID=42 \
    FASTDDS_BUILTIN_TRANSPORTS=UDPv4

# Copiar código fuente de la Api
COPY services/PiRobotDriver/agent ./services/PiRobotDriver/agent
COPY services/PiRobotDriver/inorbit_configs ./services/PiRobotDriver/inorbit_configs

COPY services/PiRobotDriver/start.sh ./start.sh
RUN chmod +x ./start.sh

ENV CAMERA_DEVICE=/dev/video0 \
    SERIAL_PORT=/dev/ttyUSB0 \
    BAUD_RATE=9600 \
    CAMERA_PUBLISH_TOPIC=/usb_cam/image_raw \
    SERIAL_PUBLISH_TOPIC=/inorbit/custom_data \
    SERIAL_SUBSCRIPTION_TOPIC=/inorbit/custom_command

CMD ["sh", "/app/start.sh", "--camera", "--robot_type", "serial"]
