#!/bin/bash
set -e

source /opt/ros/humble/setup.bash
source /ros_bridge_ws/install/setup.bash

exec "$@"
