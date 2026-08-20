IMAGE := localhost/labs-remoto/robot-driver:jazzy
DEV_IMAGE := localhost/labs-remoto/robot-driver-dev:jazzy

HOST_ARCH := $(shell uname -m)
ifeq ($(HOST_ARCH),x86_64)
DEV_PLATFORM := linux/amd64
else ifeq ($(HOST_ARCH),aarch64)
DEV_PLATFORM := linux/arm64
else
DEV_PLATFORM := linux/$(HOST_ARCH)
endif



.PHONY: container.buid
container.buid:


DEPLOY_TAR := /tmp/labs-remoto-controller-arm64.tar
PI_HOST ?= pi@raspberrypi.local
PI_DIR ?= robot-driver

.PHONY: deploy.build deploy.push deploy.up deploy.restart deploy
deploy.build:
	podman build --platform linux/arm64 --target final -t $(IMAGE) -f Dockerfile .
	podman save --format docker-archive -o $(DEPLOY_TAR) $(IMAGE)

deploy.push:
	cat $(DEPLOY_TAR) | ssh $(PI_HOST) 'docker load'
	scp compose.yaml .env.deploy.example $(PI_HOST):$(PI_DIR)/

deploy.up:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d'

deploy.restart:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d --force-recreate'

deploy: deploy.build deploy.push deploy.up

