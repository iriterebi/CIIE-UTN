#!/bin/bash
set -e

IMAGE_NAME="ros_agent"
HOST_DIR="${1:-$PWD}"

docker run -it --name $IMAGE_NAME \
    --net=host \
    --privileged \
    --cgroupns=host \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
    -v /dev:/dev \
    -v "$HOST_DIR:$HOST_DIR" \
    -w "$HOST_DIR" \
    $IMAGE_NAME

echo ">>> Docker corriendo"

