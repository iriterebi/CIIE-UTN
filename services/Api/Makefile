.PHONY: up_dev
up_dev:
	uv run fastapi dev src/server.py

.PHONY: build
build:
	docker compose build

.PHONY: up
up:
	docker compose up

.PHONY: up.detached
up.detached:
	docker compose up -d

.PHONY: down
down:
	docker compose down

.PHONY: test
test:
	uv run pytest
