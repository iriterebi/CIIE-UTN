# Quadlets — Deploy de producción con Podman

[English](README.md)

Configuración de [Podman Quadlets](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) para desplegar Labs Remoto en producción. Cada servicio corre como un contenedor gestionado por systemd.

## Arquitectura

```
Internet → [:80] Proxy (nginx) → API (FastAPI) → RosBridge (ROS 2)
                                → WebClient (Vue 3 + nginx)
                    ↕
                 PostgreSQL
```

Todos los servicios se comunican por una red interna de Podman (`labs-remoto`). Solo el proxy expone el puerto 80 al exterior.

## Servicios

| Servicio | Archivo | Imagen | Puerto externo |
|----------|---------|--------|----------------|
| **Db** | `db.container` | `postgres:17.5-alpine` | `127.0.0.1:5432` |
| **Api** | `api.container` | `localhost/labs-remoto/api` | — |
| **RosBridge** | `rosbridge.container` | `localhost/labs-remoto/rosbridge` | `127.0.0.1:9090` |
| **WebClient** | `webclient.container` | `localhost/labs-remoto/webclient` | — |
| **Proxy** | `proxy.container` | `localhost/labs-remoto/proxy` | `80` |

## Prerrequisitos

- Podman 4.4+ (soporte de Quadlets)
- Acceso root (los quadlets se instalan en `/etc/containers/systemd/`)

## Instalación

### 1. Configurar variables de entorno

Crear los archivos de entorno en `/etc/containers/env/`:

```bash
sudo mkdir -p /etc/containers/env
```

**`/etc/containers/env/db.env`**:
```env
POSTGRES_PASSWORD=<contraseña_segura>
POSTGRES_USER=<usuario>
POSTGRES_DB=ciie_db
```

**`/etc/containers/env/api.env`**:
```env
POSTGRES_PASSWORD=<contraseña_segura>
POSTGRES_USER=<usuario>
POSTGRES_DB=ciie_db
POSTGRES_URL=db:5432
ROSBRIDGE_URL=ws://rosbridge:9090
JWT_SECRET_KEY=<clave_secreta>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 2. Copiar quadlets al servidor

```bash
sudo cp quadlets/*.container quadlets/*.network quadlets/*.volume \
    /etc/containers/systemd/
sudo systemctl daemon-reload
```

### 3. Desplegar imágenes

Las imágenes se compilan localmente y se transfieren al servidor via SSH usando el script `deploy.sh`:

```bash
./quadlets/deploy.sh usuario@servidor
```

El script compila las 4 imágenes (api, webclient, rosbridge, proxy), las exporta a `.tar`, las transfiere por `scp`, las carga con `podman load` en el servidor, y reinicia todos los servicios.

### 4. Primer arranque (si no se usó deploy.sh)

```bash
# En el servidor: arrancar toda la cadena de dependencias
sudo systemctl start proxy
```

## Operaciones comunes

```bash
# Ver estado de todos los servicios
sudo systemctl status db api rosbridge webclient proxy

# Ver logs de un servicio
sudo journalctl -u api -f

# Reiniciar un servicio
sudo systemctl restart api

# Detener todo
sudo systemctl stop proxy api webclient rosbridge db

# Redesplegar después de cambios en el código
./quadlets/deploy.sh usuario@servidor
```

## Cadena de dependencias

```
db ─────────┐
             ├──► api ──────┐
rosbridge ──┘               ├──► proxy
webclient ──────────────────┘
```

`systemctl start proxy` arranca automáticamente todos los servicios necesarios en el orden correcto.

## Migraciones de base de datos

La base de datos está accesible en `127.0.0.1:5432` para ejecutar migraciones con dbmate:

```bash
cd services/Db
DATABASE_URL="postgres://<usuario>:<contraseña>@127.0.0.1:5432/ciie_db?sslmode=disable" \
    dbmate up
```

## Notas

- **Sin TLS**: esta configuración no incluye TLS. Para producción con HTTPS, agregar un reverse proxy externo con certbot o montar certificados en el contenedor proxy.
- **Intranet**: las rutas `/m2m/` y `/rosbridge/` están restringidas a IPs privadas en la configuración de nginx. Verificar que las restricciones funcionen correctamente con la red de Podman.
- **Logs**: usar `journalctl -u <servicio>` para ver logs, ya que systemd captura stdout/stderr de los contenedores.
