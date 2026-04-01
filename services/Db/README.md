# /Db · Database

This section contains the project's database definition, using Postgresql as the database engine.

The configuration is designed to run the Database using Docker.

There is a [Makefile](https://www.google.com/search?q=./Makefile) with useful commands. To get specific information about this Makefile, run:

```shell
make help
```

## Container Types

There is a [compose.yaml](https://www.google.com/search?q=./compose.yaml) file designed to be used with Docker Compose.

There are 2 types of containers:

  - ### Database

    These are the Postgres containers with environment-specific configurations.

      - `db-prod`
        Container configured to be used in a **Production** environment.
      - `db-dev`
        Container configured to be used in a **Development** environment.
      - `db-dev-ephimeral`
        Container configured to be used in **Development** and **Tests** environments. \<br\>
        Unlike `db-dev`, `db-dev-ephimeral` **does not persist the database** between runs, making it especially useful for tests.

  - ### Utilities

    These containers are intended as tools for the development and administration of the database.

      - dbmate
        Container in charge of managing database migrations using the [dbmate](https://www.google.com/search?q=https%27://github.com/amacneil/dbmate%3Ftab%3Dreadme-ov-file) software.

## Starting the DB for development

```shell
# For development we have 2 options: db-dev and db-dev-ephimeral
# just run the make command you need, for example:

make up_db.dev
# or make up_db.dev.detached to run it in the background
# and in another shell run
make migrate_db
# although this is only necessary the first time, it is recommended to run the migrations
# every time the DB is run to keep its definition synchronized

## --- or if you don't want to persist the DB ---
make up_db.ephimeral # or make up_db.ephimeral.detached to run it in the background
# and in another shell run
make migrate_db # mandatory

```

## `make help`

```
$ make help
----------------------------------------------------------------------
This Makefile defines frequent commands for the administration of
Docker containers related to the database.
----------------------------------------------------------------------
up_db.dev
        Runs the db-dev container in the current shell.

up_db.dev.detached
        same as up_db.dev but running the container in the background.

down_db.dev.detached
        Stops the db-dev container running in the background.

up_db.ephimeral
        Runs the db-dev-ephimeral container in the current shell.

up_db.ephimeral.detached
        same as up_db.ephimeral but running the container in the background.

down_db.ephimeral.detached
        Stops the db-dev-ephimeral container running in the background.

migrate_db
        Creates or updates the database

help
        Show this help.
```
