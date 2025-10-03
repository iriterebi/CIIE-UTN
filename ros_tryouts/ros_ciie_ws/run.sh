#!/bin/bash
set -e

IMAGE_NAME="ros-ciie"

# Cargar puerto USB si existe .env
if [ -f .env ]; then
    source config/.env
fi

DEVICE_FLAG=""
if [ ! -z "$USB_PORT" ] && [ -e "$USB_PORT" ]; then
    DEVICE_FLAG="--device=$USB_PORT"
    echo ">>> Montando USB: $USB_PORT"
fi

docker run -it --rm \
    -v $(pwd):/ros_ciie_ws \
    $DEVICE_FLAG \
    --privileged \
    $IMAGE_NAME
