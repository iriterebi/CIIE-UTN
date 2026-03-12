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

# --- WebClient ---

.PHONY: webclient.build
webclient.build:			## Construye la imagen Docker del frontend Vue.
	$(MAKE) -C WebClient build

.PHONY: webclient.up
webclient.up:				## Ejecuta el frontend Vue en foreground.
	$(MAKE) -C WebClient up_dev

.PHONY: webclient.up.detached
webclient.up.detached:			## Ejecuta el frontend Vue en background.
	$(MAKE) -C WebClient up_dev.detached

.PHONY: webclient.down
webclient.down:				## Detiene el frontend Vue.
	$(MAKE) -C WebClient down_dev

# --- RosBridge ---

.PHONY: rosbridge.up
rosbridge.up:				## Ejecuta rosbridge en foreground.
	$(MAKE) -C RosBridge up_dev

.PHONY: rosbridge.up.detached
rosbridge.up.detached:			## Ejecuta rosbridge en background.
	$(MAKE) -C RosBridge up_dev.detached

.PHONY: rosbridge.down
rosbridge.down:				## Detiene rosbridge.
	$(MAKE) -C RosBridge down_dev

.PHONY: rosbridge.demo
rosbridge.demo:				## Ejecuta rosbridge en modo demo (foreground).
	$(MAKE) -C RosBridge up_demo

.PHONY: rosbridge.demo.detached
rosbridge.demo.detached:		## Ejecuta rosbridge en modo demo (background).
	$(MAKE) -C RosBridge up_demo.detached

.PHONY: rosbridge.demo.down
rosbridge.demo.down:			## Detiene rosbridge demo.
	$(MAKE) -C RosBridge down_demo

# --- Compuestos ---

.PHONY: up
up: db.up.detached api.up		## Ejecuta DB (background) + API (foreground).

.PHONY: up.all
up.all: db.up.detached webclient.up.detached rosbridge.up.detached api.up	## Ejecuta DB + WebClient + RosBridge (background) + API (foreground).

.PHONY: down
down: db.down webclient.down rosbridge.down	## Detiene todos los servicios en background.

# --- Help ---

.PHONY: help
help:					## Muestra esta ayuda.
	@grep -E '^[a-zA-Z_.]+:.*##' $(MAKEFILE_LIST) | \
		awk -F ':.*## ' '{printf "  \033[36m%-30s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
