#!/bin/bash
set -e

IMAGE_NAME="ros-ciie"

# 1. Cargar puerto USB si existe .env (asumo que .env tiene USB_PORT=...)
if [ -f config/.env ]; then
    source config/example.env
fi

# El puerto USB_PORT de tu .env debería ser el nombre corto, 
# ej: USB_PORT=/dev/ttyACM0 o /dev/ttyUSB0.
# Si tu .env usa el nombre largo, ¡debes cambiarlo!

DEVICE_FLAG=""
ENV_FLAG=""

if [ ! -z "$USB_PORT" ] && [ -e "$USB_PORT" ]; then
    # Monta el dispositivo en el contenedor
    DEVICE_FLAG="--device=$USB_PORT:$USB_PORT"
    
    # Pasa el nombre corto del puerto al agente ROS
    ENV_FLAG="-e SERIAL_PORT=$USB_PORT"

    echo ">>> Montando USB: $USB_PORT"
fi

# Nota: El flag --privileged ayuda con los permisos, pero a veces no es suficiente
# por lo que incluimos el ENV_FLAG para que el agente sepa el nombre del puerto.
docker run -it --rm \
    -v $(pwd):/ros_ciie_ws \
    $DEVICE_FLAG \
    $ENV_FLAG \
    --privileged \
    $IMAGE_NAME
