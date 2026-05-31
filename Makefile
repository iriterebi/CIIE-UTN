## ----------------------------------------------------------------------
## Makefile raíz — orquesta los subproyectos del sistema.
## Uso: make help
## ----------------------------------------------------------------------

## --- Api ---

.PHONY: api.up
api.up:					## Ejecuta la API en modo desarrollo.
	$(MAKE) -C services/Api up_dev

## --- Db ---

.PHONY: db.up
db.up:					## Ejecuta la base de datos en foreground.
	$(MAKE) -C services/Db up_db.dev

.PHONY: db.up.detached
db.up.detached:				## Ejecuta la base de datos en background.
	$(MAKE) -C services/Db up_db.dev.detached

.PHONY: db.down
db.down:				## Detiene la base de datos en background.
	$(MAKE) -C services/Db down_db.dev.detached

.PHONY: db.up.ephimeral
db.up.ephimeral:			## Ejecuta la base de datos efímera (tmpfs) en foreground.
	$(MAKE) -C services/Db up_db.ephimeral

.PHONY: db.up.ephimeral.detached
db.up.ephimeral.detached:		## Ejecuta la base de datos efímera en background.
	$(MAKE) -C services/Db up_db.ephimeral.detached

.PHONY: db.down.ephimeral
db.down.ephimeral:			## Detiene la base de datos efímera en background.
	$(MAKE) -C services/Db down_db.ephimeral.detached

.PHONY: db.migrate
db.migrate:				## Ejecuta las migraciones de la base de datos.
	$(MAKE) -C services/Db migrate_db

.PHONY: db.seed
db.seed:				## Aplica los datos semilla.
	$(MAKE) -C services/Db seed_apply

## --- WebClient ---

.PHONY: webclient.build
webclient.build:			## Construye la imagen Docker del frontend Vue.
	$(MAKE) -C services/WebClient build

.PHONY: webclient.up
webclient.up:				## Ejecuta el frontend Vue en foreground.
	$(MAKE) -C services/WebClient up_dev

.PHONY: webclient.up.detached
webclient.up.detached:			## Ejecuta el frontend Vue en background.
	$(MAKE) -C services/WebClient up_dev.detached

.PHONY: webclient.down
webclient.down:				## Detiene el frontend Vue.
	$(MAKE) -C services/WebClient down_dev

## --- Compuestos ---

.PHONY: up
up: db.up.detached api.up		## Ejecuta DB (background) + API (foreground).

.PHONY: up.all
up.all: db.up.detached webclient.up.detached api.up	## Ejecuta DB + WebClient (background) + API (foreground).

.PHONY: down
down: db.down webclient.down		## Detiene todos los servicios en background.

## --- Help ---

.PHONY: help
help:					## Muestra esta ayuda.
	@grep -E '^(## |[a-zA-Z_.]+:.*##)' $(MAKEFILE_LIST) | \
		awk -F ':' '{ \
			if ($$0 ~ /^## /) { sub(/^## /, "", $$0); printf "  %s\n", $$0 } \
			else { split($$0, a, /:.*## /); printf "    \033[36m%-28s\033[0m %s\n", a[1], a[2] } \
		}'

.DEFAULT_GOAL := help
