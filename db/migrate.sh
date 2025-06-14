#! /usr/bin/env bash

docker compose exec db /usr/db-migrations/migrate.sh
