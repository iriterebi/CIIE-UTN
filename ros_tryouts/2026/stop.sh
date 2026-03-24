#!/bin/bash
set -e

IMAGE_NAME="ros_agent"

echo ">>> Deteniendo contenedor: $IMAGE_NAME"
docker stop $IMAGE_NAME 2>/dev/null || echo ">>> Contenedor no estaba corriendo."

echo ">>> Eliminando contenedor: $IMAGE_NAME"
docker rm $IMAGE_NAME 2>/dev/null || echo ">>> Contenedor no existía."

echo ">>> Listo."