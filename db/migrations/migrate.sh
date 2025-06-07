#!/usr/bin/env bash

set -e

cd /usr/db-migrations/

for m in ./*.sql; do
    # TODO usar .env para las credenciales
    mysql --password=jesus123 --user=root < $m
done