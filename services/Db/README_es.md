# /Db · Base de Datos
En esta sección se encuentra la deficnión de la base de Datos del proyecto,
utilizando Postgresql como motor de base de datos.

La configuración está pensada para ejecutar la Base de Datos utilizando Docker.

Se cuenta con un [Makefile](./Makefile) con comandos útiles. Para obtener información específica de
este Makefile, ejecutar:
```shell
make help
```

## Tipos de contenedores

Se cuenta con un archivo [compose.yaml](./compose.yaml) pensado para ser utilizado con Docker Compose.

Hay 2 tipos de contenedores

- ### Base de Datos

    son los contenedores de Postgres con configuraciones epecíficas de ambiente

    - `db-prod`

        Contenedor configurado para ser utilizado en ambiente de **Producción**

    - `db-dev`

        Contenedor configurado para ser utilizado en ambiente de **Desarrollo**

    - `db-dev-ephimeral`

        Contenedor configurado para ser utilizado en ambiente de **Desarrollo** y **Tests**. <br>
        A diferencia de `db-dev`, `db-dev-ephimeral` **No persiste la base de datos**
        entre ejecuciones, haciéndolo especialmente útil para pruebas.


- ### Utilitarios

    Estos contenedores están pensados como herramientas para el desarrollo y administración de la base de datos.

    - dbmate

        Contenedor encargado de administrar las migraciones de la base de datos utilizando el
        software [dbmate](https://github.com/amacneil/dbmate?tab=readme-ov-file).



## Puesta en marcha de la DB para desarrollo

```shell
# Para desarrollo tenemos 2 opciones: db-dev y db-dev-ephimeral
# basta con ejecutar el comando make que se necesite, por ejemplo:

make up_db.dev
# o make up_db.dev.detached para ejecutarlo en background
# y en otra shell ejecturar
make migrate_db
# si bien, esto solo es necesario la primera vez, es recomendable correr las migraciones
# cada vez que se ejecuta la DB para mantener sicronizada su definición

## --- o si no se quiere persisr la DB ---
make up_db.ephimeral # o make up_db.ephimeral.detached para ejecutarlo en background
# y en otra shell ejecturar
make migrate_db # obligatorio

```
## `make help`
```
$ make help
----------------------------------------------------------------------
Este Makefile define comandos frecuentes para la administración de los
contenedores Docker relacionados con la base de datos.
----------------------------------------------------------------------
up_db.dev
        Ejecuta el contenedor de db-dev en la shell actual.

up_db.dev.detached
        igual que up_db.dev pero ejecutando el contenedor en background.

down_db.dev.detached
        Detiene el contenedor db-dev ejecutandose en background.

up_db.ephimeral
        Ejecuta el contenedor de db-dev-ephimeral en la shell actual.

up_db.ephimeral.detached
        igual que up_db.ephimeral pero ejecutando el contenedor en background.

down_db.ephimeral.detached
        Detiene el contenedor db-dev-ephimeral ejecutandose en background.

migrate_db
        Crea o actualiza la base de datos

help
        Show this help.
```
