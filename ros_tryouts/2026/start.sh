#!/bin/bash

set -e

SESSION="ros_agent_session"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

sudo "$SCRIPT_DIR/docker/build.sh"

sudo "$SCRIPT_DIR/docker/run.sh" "$PWD"