#!/bin/bash
set -e

IMAGE_NAME="ros_agent"

echo ">>> Construyendo imagen Docker: $IMAGE_NAME"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)
docker build -t $IMAGE_NAME -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"

echo ">>> Imagen construida con éxito."
