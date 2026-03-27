# Dockerfile — Api (producción)
# Multi-stage build con uv para instalar dependencias

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Copiar archivos de workspace (raíz + Api)
COPY pyproject.toml /app/pyproject.toml
COPY Api/pyproject.toml /app/Api/pyproject.toml

# Instalar dependencias sin el código fuente (cacheo de capas)
RUN uv sync --package ciie-remote-lab-api --no-dev --no-install-workspace

# Copiar código fuente de la Api
COPY Api/src /app/Api/src

# Instalar el paquete del workspace
RUN uv sync --package ciie-remote-lab-api --no-dev


FROM docker.io/library/python:3.13-slim-bookworm

WORKDIR /app

# Copiar el entorno virtual completo
COPY --from=builder /app/.venv /app/.venv

# Copiar código fuente
COPY Api/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["fastapi", "run", "src/server.py", "--host", "0.0.0.0", "--port", "8000"]
