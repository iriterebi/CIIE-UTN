#!/bin/bash
set -e
sudo apt-get install -y systemd
sudo ./build.sh
source config/.env
sudo ./run.sh