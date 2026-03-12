## ----------------------------------------------------------------------
## Este Makefile define comandos frecuentes para el frontend web.
## ----------------------------------------------------------------------


.PHONY: up_dev
up_dev:					## Ejecuta el contenedor web en foreground.
	docker compose up app-dev

.PHONY: up_dev.detached
up_dev.detached:			## Ejecuta el contenedor web en background.
	docker compose up -d app-dev

.PHONY: down_dev
down_dev:				## Detiene el contenedor web.
	docker compose down app-dev

.PHONY: help
help:					## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
