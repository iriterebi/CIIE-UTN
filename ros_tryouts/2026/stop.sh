#!/bin/bash

DOCKER_NAME="ciie-jazzy-agent"

echo ">>> Stopping container: ${DOCKER_NAME}"
docker stop "${DOCKER_NAME}" 2>/dev/null || echo ">>> Container was not running."

echo ">>> Done."
