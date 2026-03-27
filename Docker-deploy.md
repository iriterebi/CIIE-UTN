## Docker Deploy (dev)

### Primera vez con Docker

1. Copiar los archivos `.env.example` a `.env` en cada subproyecto que lo requiera (`Api/`, `Db/`) y completar con los datos correspondientes (ver sección de variables de entorno en `README.es.md`).
2. Crear la red Docker compartida:
```shell
docker network create ciie-test
```

### Levantar todo el sistema

Desde la raíz del proyecto:
```shell
# Levantar DB (background) + WebClient + RosBridge (background) + API (foreground)
make up.all

# O solo DB + API (lo mínimo para desarrollo backend)
make up
```

Para detener los servicios en background:
```shell
make down
```

### Servicios individuales

#### Base de datos
```shell
make db.up                    # Foreground
make db.up.detached           # Background
make db.down                  # Detener

# Primera vez: ejecutar migraciones y datos semilla
make db.migrate
make db.seed
```

#### API (FastAPI)
```shell
make api.up                   # Ejecuta: uv run fastapi dev src/server.py
```

#### WebClient (Vue 3)
```shell
make webclient.build          # Construir imagen Docker
make webclient.up             # Foreground
make webclient.up.detached    # Background
make webclient.down           # Detener
```

#### RosBridge
```shell
make rosbridge.up             # Foreground
make rosbridge.up.detached    # Background
make rosbridge.down           # Detener
```

### Acceso

- **WebClient**: http://localhost:3000
- **API**: http://localhost:8000
- **RosBridge WS**: ws://localhost:9090

### Ver todos los comandos disponibles
```shell
make help
```
