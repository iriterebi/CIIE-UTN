.PHONY: up_dev
up_dev:
	uv run -m controller

.DEFAULT_GOAL := up_dev

# --- ROS 2 (Jazzy) en Podman: correr Ros2Strategy con rclpy real ---
# Requiere podman instalado (ver sección "Correr Ros2Strategy con Podman" en CLAUDE.md).
# Podman es rootless: no necesita grupo ni daemon.
# Prefijo localhost/ porque podman guarda las imágenes locales en ese namespace.
# IMAGE (stage `final`, deploy) y DEV_IMAGE (stage `base`, solo dev) usan nombres de
# repo DISTINTOS a propósito: los dos stages del Dockerfile ya no son idénticos, así
# que compartir un tag arriesgaría pisar el artefacto de deploy con la imagen de dev
# (o viceversa) según el orden en que se corran los targets.
IMAGE := localhost/labs-remoto/controller:jazzy
DEV_IMAGE := localhost/labs-remoto/controller-dev:jazzy

# `deploy.build` cruza arquitectura (--platform linux/arm64) contra la MISMA referencia
# de imagen base (docker.io/library/ros:jazzy) que usa `ros.build`. El storage local de
# podman guarda una sola arquitectura por tag, así que un build pisa la caché del otro
# según el orden en que se corran — ros.build queda con la base arm64 y explota con
# "Exec format error" al ejecutar apt-get. Fijar --platform al arch nativo del host en
# ros.build fuerza a podman a repullear la base correcta si hace falta, en vez de asumir
# que la caché ya la tiene.
HOST_ARCH := $(shell uname -m)
ifeq ($(HOST_ARCH),x86_64)
DEV_PLATFORM := linux/amd64
else ifeq ($(HOST_ARCH),aarch64)
DEV_PLATFORM := linux/arm64
else
DEV_PLATFORM := linux/$(HOST_ARCH)
endif

.PHONY: ros.build ros.verify ros.test ros.shell ros.run
ros.build:
	podman build --platform $(DEV_PLATFORM) --target base -f Dockerfile -t $(DEV_IMAGE) .

ros.verify:
	podman run --rm $(DEV_IMAGE) \
		python -c "import rclpy; from std_msgs.msg import String; print('rclpy + std_msgs OK')"

ros.test:
	# PYTEST_DISABLE_PLUGIN_AUTOLOAD evita que los plugins pytest de ROS
	# (launch_testing, etc., visibles vía --system-site-packages) choquen con pytest 9.x.
	podman run --rm -e PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 -v "$(CURDIR)":/app $(DEV_IMAGE) python -m pytest

ros.shell:
	podman run --rm -it --network=host -v "$(CURDIR)":/app $(DEV_IMAGE) bash

ros.run:
	podman run --rm --network=host -v "$(CURDIR)":/app -e LOCAL_STRATEGY=Ros2Strategy $(DEV_IMAGE)

# --- Deploy a la Pi (Docker) --------------------------------------------------
# Build con PODMAN en dev (docker no está instalado en dev), save como docker-archive
# (tar que `docker load` acepta en la Pi), load por SSH. Cross-build arm64 requiere
# binfmt qemu registrado en el host (paquete qemu-user-static).
DEPLOY_TAR := /tmp/labs-remoto-controller-arm64.tar
PI_HOST ?= pi@raspberrypi.local
PI_DIR ?= labs-remoto-controller

.PHONY: deploy.build deploy.push deploy.up deploy.restart deploy
deploy.build:
	podman build --platform linux/arm64 --target final -t $(IMAGE) -f Dockerfile .
	podman save --format docker-archive -o $(DEPLOY_TAR) $(IMAGE)

deploy.push:
	cat $(DEPLOY_TAR) | ssh $(PI_HOST) 'docker load'
	ssh $(PI_HOST) 'mkdir -p $(PI_DIR)/data'
	scp compose.yaml robot-cli .env.deploy.example $(PI_HOST):$(PI_DIR)/

deploy.up:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d'

deploy.restart:
	ssh $(PI_HOST) 'cd $(PI_DIR) && docker compose up -d --force-recreate'

deploy: deploy.build deploy.push deploy.up
