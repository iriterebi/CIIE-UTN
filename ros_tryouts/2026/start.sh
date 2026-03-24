#!/bin/bash

set -e

SESSION="ros_agent_session"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

sudo "$SCRIPT_DIR/docker/build.sh"

sudo "$SCRIPT_DIR/docker/run.sh" "$PWD"

apt-get install -y tmux
./tmux-start.sh

if [ !-d "opt/$SESSION" ]; then
    curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh
fi