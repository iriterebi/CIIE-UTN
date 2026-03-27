## ----------------------------------------------------------------------
## Este Makefile define comandos frecuentes para la administración de los
## contenedores Docker relacionados con la base de datos.
## ----------------------------------------------------------------------


.PHONY: up_db.dev
up_db.dev:				## Ejecuta el contenedor de db-dev en la shell actual.
	docker compose up db-dev

.PHONY: up_db.dev.detached
up_db.dev.detached:			## igual que up_db.dev pero ejecutando el contenedor en background.
	docker compose up -d db-dev

.PHONY: down_db.dev.detached
down_db.dev.detached:			## Detiene el contenedor db-dev ejecutandose en background.
	docker compose down db-dev

.PHONY: up_db.ephimeral
up_db.ephimeral:			## Ejecuta el contenedor de db-dev-ephimeral en la shell actual.
	docker compose up db-dev-ephimeral

.PHONY: up_db.ephimeral
up_db.ephimeral.detached:		## igual que up_db.ephimeral pero ejecutando el contenedor en background.
	docker compose up -d db-dev-ephimeral

.PHONY: down_db.ephimeral.detached
down_db.ephimeral.detached:		## Detiene el contenedor db-dev-ephimeral ejecutandose en background.
	docker compose down db-dev-ephimeral

.PHONY: migrate_db
migrate_db:				## Crea o actualiza la base de datos
	docker compose run --rm --remove-orphans -i dbmate up

.PHONY: seed_apply
seed_apply:
	docker compose run --rm --remove-orphans -i dbmate --migrations-dir "/seed/migrations" --migrations-table "seeds_schema_migrations" migrate

.PHONY: help
help:					## Show this help.
	@sed -ne '/@sed/!s/## //p' $(MAKEFILE_LIST)

