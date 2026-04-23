#!/bin/bash
set -e

IMAGE_NAME="ros_agent"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)

if docker image inspect "$IMAGE_NAME" > /dev/null 2>&1 && [ "${FORCE_BUILD:-0}" != "1" ]; then
    echo ">>> Imagen $IMAGE_NAME ya existe, omitiendo build. Usá FORCE_BUILD=1 para reconstruir."
    exit 0
fi

echo ">>> Construyendo imagen Docker: $IMAGE_NAME"
docker build -t $IMAGE_NAME -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"

echo ">>> Imagen construida con éxito."
