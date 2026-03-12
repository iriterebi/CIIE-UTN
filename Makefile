## ----------------------------------------------------------------------
## Makefile raíz — orquesta los subproyectos del sistema.
## Uso: make help
## ----------------------------------------------------------------------


# --- Api ---

.PHONY: api.up
api.up:					## Ejecuta la API en modo desarrollo.
	$(MAKE) -C Api up_dev

# --- Db ---

.PHONY: db.up
db.up:					## Ejecuta la base de datos en foreground.
	$(MAKE) -C Db up_db.dev

.PHONY: db.up.detached
db.up.detached:				## Ejecuta la base de datos en background.
	$(MAKE) -C Db up_db.dev.detached

.PHONY: db.down
db.down:				## Detiene la base de datos en background.
	$(MAKE) -C Db down_db.dev.detached

.PHONY: db.up.ephimeral
db.up.ephimeral:			## Ejecuta la base de datos efímera (tmpfs) en foreground.
	$(MAKE) -C Db up_db.ephimeral

.PHONY: db.up.ephimeral.detached
db.up.ephimeral.detached:		## Ejecuta la base de datos efímera en background.
	$(MAKE) -C Db up_db.ephimeral.detached

.PHONY: db.down.ephimeral
db.down.ephimeral:			## Detiene la base de datos efímera en background.
	$(MAKE) -C Db down_db.ephimeral.detached

.PHONY: db.migrate
db.migrate:				## Ejecuta las migraciones de la base de datos.
	$(MAKE) -C Db migrate_db

.PHONY: db.seed
db.seed:				## Aplica los datos semilla.
	$(MAKE) -C Db seed_apply

# --- Web ---

.PHONY: web.up
web.up:					## Ejecuta el frontend web en foreground.
	$(MAKE) -C Web up_dev

.PHONY: web.up.detached
web.up.detached:			## Ejecuta el frontend web en background.
	$(MAKE) -C Web up_dev.detached

.PHONY: web.down
web.down:				## Detiene el frontend web en background.
	$(MAKE) -C Web down_dev

# --- Compuestos ---

.PHONY: up
up: db.up.detached api.up		## Ejecuta DB (background) + API (foreground).

.PHONY: up.all
up.all: db.up.detached web.up.detached api.up	## Ejecuta DB + Web (background) + API (foreground).

.PHONY: down
down: db.down web.down			## Detiene todos los servicios en background.

# --- Help ---

.PHONY: help
help:					## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
