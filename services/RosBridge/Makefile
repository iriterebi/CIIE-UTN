## ----------------------------------------------------------------------
## Este Makefile define comandos frecuentes para el servicio ROS Bridge.
## ----------------------------------------------------------------------


.PHONY: up
up:				## Ejecuta rosbridge en foreground.
	docker compose up rosbridge

.PHONY: up.detached
up.detached:			## Ejecuta rosbridge en background.
	docker compose up -d rosbridge

.PHONY: down
down:				## Detiene rosbridge.
	docker compose down rosbridge

.PHONY: build
build:				## Construye la imagen Docker.
	docker compose build

.PHONY: help
help:				## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
