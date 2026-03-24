#!/bin/bash
set -e

IMAGE_NAME="ros_agent"

docker run -it --name $IMAGE_NAME \
    --net=host \
    --privileged \
    -v /dev:/dev \
    $IMAGE_NAME