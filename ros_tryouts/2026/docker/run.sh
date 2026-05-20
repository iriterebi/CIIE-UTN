#!/bin/bash
set -e

DOCKER_IMAGE="ros_agent"
DOCKER_NAME="ciie-jazzy-agent"
SOURCES=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
USB_ARG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -p)
            shift
            USB_ARG="--device /dev/$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Starting '${DOCKER_NAME}' (image: ${DOCKER_IMAGE})"
echo "Mounting workspace from: ${SOURCES}"
[ -n "$USB_ARG" ] && echo "USB device: ${USB_ARG#--device }"

# Remove any previous instance with the same name
docker rm -f "${DOCKER_NAME}" 2>/dev/null || true

docker run --detach --privileged \
    -v "${SOURCES}:/root/workspace" \
    -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
    ${WITH_DISPLAY:+ \
    -v /tmp/.X11-unix:/tmp/.X11-unix \
    -v $HOME/.Xauthority:/root/.Xauthority \
    -e DISPLAY=$DISPLAY \
    } \
    --tmpfs /run \
    --cgroupns=host \
    --network host \
    --name "${DOCKER_NAME}" \
    --hostname "${DOCKER_NAME}" \
    --add-host "${DOCKER_NAME}:127.0.0.1" \
    --rm \
    ${USB_ARG} \
    "${DOCKER_IMAGE}"

echo "Waiting for systemd to initialize..."
sleep 2

echo "Attaching to tmux session..."
docker exec -it "${DOCKER_NAME}" bash /root/tmux-start.sh
