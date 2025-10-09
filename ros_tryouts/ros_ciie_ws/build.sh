#!/bin/bash
set -e

IMAGE_NAME="ros-ciie"

echo ">>> Construyendo imagen Docker: $IMAGE_NAME"
docker build -t $IMAGE_NAME .

echo ">>> Imagen construida con éxito."
