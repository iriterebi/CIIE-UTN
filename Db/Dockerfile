# Dockerfile

# ===== Etapa 1: Builder =====
# Usamos una imagen ligera para descargar el binario de dbmate.
# Esto mantiene la imagen final limpia y sin herramientas de construcción.
FROM alpine:3.20 AS dbmate-builder

# Argumento para especificar la versión de dbmate y facilitar actualizaciones
ARG DBMATE_VERSION=2.27.0

# Descargamos el binario de dbmate para Linux AMD64 y lo hacemos ejecutable
RUN apk add --no-cache curl \
    && curl -fsSL -o /dbmate "https://github.com/amacneil/dbmate/releases/download/v${DBMATE_VERSION}/dbmate-linux-amd64" \
    && chmod +x /dbmate

# ==================================
# ===== Stage 2: Production =======
# ==================================
# Stage para el entorno de producción.
# Crea una imagen auto-contenida con las migraciones dentro.
FROM mysql:8 AS prod

# Copia dbmate desde el builder
COPY --from=dbmate-builder /dbmate /usr/local/bin/dbmate

# Copia las migraciones y el script de inicialización DENTRO de la imagen
COPY ./def /db
COPY ./init-db.sh /docker-entrypoint-initdb.d/init-db.sh


# ==================================
# ===== Stage 3: Development =======
# ==================================
# Stage para el entorno de desarrollo.
# NO copia la carpeta /def, ya que se montará como un volumen.
FROM mysql:8 AS dev

# Copia dbmate desde el builder
COPY --from=dbmate-builder /dbmate /usr/local/bin/dbmate

# Copia solo el script de inicialización. La carpeta /db se montará externamente.
COPY ./init-db.sh /docker-entrypoint-initdb.d/init-db.sh
