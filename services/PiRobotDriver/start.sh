#!/bin/bash

set -e

cd /root/agent/


(cd ./serial_scraper/ && python3 ./scraper.py)
