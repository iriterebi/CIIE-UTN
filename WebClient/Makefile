## ----------------------------------------------------------------------
## Makefile — WebClient (Vue 3 + Vite + PicoCSS)
## Uso: make help
## ----------------------------------------------------------------------

.PHONY: build
build:				## Construye la imagen Docker.
	docker compose build

.PHONY: up_dev
up_dev:				## Ejecuta el cliente web en foreground.
	docker compose --profile dev up webclient

.PHONY: up_dev.detached
up_dev.detached:		## Ejecuta el cliente web en background.
	docker compose --profile dev up -d webclient

.PHONY: down_dev
down_dev:			## Detiene el cliente web.
	docker compose --profile dev down

.PHONY: dev
dev:				## Ejecuta el servidor de desarrollo Vite (sin Docker).
	npm run dev

.PHONY: help
help:				## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
