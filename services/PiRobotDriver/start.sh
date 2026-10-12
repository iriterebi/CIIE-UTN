#!/usr/bin/env bash

set -e

cd /app/services/PiRobotDriver/

python3 -m agent "$@"
