# Dockerfile — Api (producción)
# Multi-stage build con uv para instalar dependencias

FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

# Sin descargas de Python: el venv se copia al stage final, así que debe usar
# el intérprete del sistema (misma versión menor que el runtime). Si uv
# descargara uno propio, el venv quedaría apuntando a un python inexistente.
ENV UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Copiar archivos de workspace (raíz + Api)
COPY pyproject.toml /app/pyproject.toml
COPY services/Api/pyproject.toml /app/services/Api/pyproject.toml
COPY uv.lock /app/uv.lock

# Instalar dependencias sin el código fuente (cacheo de capas)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --package ciie-remote-lab-api --no-dev --no-install-workspace

# Copiar código fuente de la Api
COPY services/Api/src /app/services/Api/src

# Instalar el paquete del workspace
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package ciie-remote-lab-api --no-dev


FROM docker.io/library/python:3.14-slim-bookworm

WORKDIR /app

# Copiar el entorno virtual completo
COPY --from=builder /app/.venv /app/.venv

# Copiar código fuente
COPY services/Api/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["fastapi", "run", "src/server.py", "--host", "0.0.0.0", "--port", "8000"]
