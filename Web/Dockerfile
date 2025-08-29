FROM php:8.2-apache-bookworm

# RUN apt-get update && docker-php-ext-install pdo_mysql && docker-php-ext-install mysqli
RUN apt-get update && apt-get install -y libpq-dev && docker-php-ext-install pdo_pgsql

# Use the default production configuration
RUN mv "$PHP_INI_DIR/php.ini-production" "$PHP_INI_DIR/php.ini"

COPY php.ini "$PHP_INI_DIR/conf.d/001-php.ini"
