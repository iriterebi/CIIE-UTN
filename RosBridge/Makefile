## ----------------------------------------------------------------------
## Este Makefile define comandos frecuentes para el servicio ROS Bridge.
## ----------------------------------------------------------------------


.PHONY: up_dev
up_dev:				## Ejecuta rosbridge en foreground (requiere nodos ROS externos).
	docker compose up rosbridge

.PHONY: up_dev.detached
up_dev.detached:		## Ejecuta rosbridge en background.
	docker compose up -d rosbridge

.PHONY: down_dev
down_dev:			## Detiene rosbridge.
	docker compose down rosbridge

.PHONY: up_demo
up_demo:			## Ejecuta rosbridge + nodo mock en foreground (modo demo).
	docker compose up rosbridge-demo

.PHONY: up_demo.detached
up_demo.detached:		## Ejecuta rosbridge + nodo mock en background (modo demo).
	docker compose up -d rosbridge-demo

.PHONY: down_demo
down_demo:			## Detiene rosbridge demo.
	docker compose down rosbridge-demo

.PHONY: build
build:				## Construye la imagen Docker.
	docker compose build

.PHONY: help
help:				## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
