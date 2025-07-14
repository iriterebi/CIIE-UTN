#!/bin/sh

# Detiene la ejecución si algún comando falla
set -e

# dbmate necesita la variable DATABASE_URL para conectarse.
# La construimos usando las variables de entorno que provee la imagen de mysql.
# Es importante usar 127.0.0.1 porque el script se ejecuta en un servidor temporal localmente.
export DATABASE_URL="mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@127.0.0.1:3306/${MYSQL_DATABASE}"

pwd

# Nos movemos al directorio donde están los archivos de dbmate
cd /db

pwd
echo "⏳ Esperando a que la base de datos esté lista..."
dbmate wait

echo "🚀 Ejecutando migraciones de la base de datos..."
dbmate --migrations-dir ./migrations up

echo "✅ Migraciones completadas exitosamente."
