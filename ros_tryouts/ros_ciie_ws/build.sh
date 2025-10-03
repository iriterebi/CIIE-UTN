#!/bin/bash
set -e

IMAGE_NAME="ros-ciie"

echo ">>> Construyendo imagen Docker: $IMAGE_NAME"
docker build -t $IMAGE_NAME .

echo ">>> Imagen construida con éxito."
echo ">>> Para correr el contenedor con tu src/ montado:"
echo "1. Copiá config/example.env a config/.env y configurá USB  y BaudRate"
echo "2. Ejecutá: ./run.sh"
