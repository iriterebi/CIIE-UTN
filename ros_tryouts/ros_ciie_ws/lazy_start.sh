#!/bin/bash
set -e
sudo ./build.sh
source config/.env
sudo ./run.sh