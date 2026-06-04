#!/bin/bash
set -e

IMAGE_NAME="ros_agent"
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/../../.." && pwd)

echo ">>> Building image '${IMAGE_NAME}' (context: ${REPO_ROOT})"
docker build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/Dockerfile" "${REPO_ROOT}"

echo ">>> Image built successfully."
