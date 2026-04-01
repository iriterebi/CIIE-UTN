---
name: sync-quadlets
description: >
  Sincronizar los archivos de quadlets de producción cuando cambia la configuración de
  compilación o deploy de algún servicio. Usar automáticamente cuando se modifica un Dockerfile,
  una config de nginx de producción, variables de entorno de producción, dependencias de un
  servicio, puertos expuestos, o el script deploy.sh. También disparar cuando se agrega o
  elimina un servicio del sistema.
argument-hint: "[all | api | webclient | rosbridge | proxy | db] (uno, varios separados por espacio, o all)"
allowed-tools: Read, Edit, Write, Glob, Grep, Bash(ls *)
---

# Sync Quadlets

Sincronizar los archivos de quadlets en `quadlets/` para que reflejen el estado actual de la configuración de compilación/deploy de los servicios.

## Argumentos

`$ARGUMENTS` indica qué servicios sincronizar:

- `all` o vacío → todos los servicios
- Uno o más nombres separados por espacio: `api`, `webclient`, `rosbridge`, `proxy`, `db`

Ejemplos:
- `/sync-quadlets all`
- `/sync-quadlets api`
- `/sync-quadlets api proxy`

## Archivos fuente → archivos quadlet

Para cada servicio, leer la configuración fuente y actualizar el quadlet correspondiente:

| Servicio | Fuentes a revisar | Quadlet |
|----------|------------------|---------|
| **db** | `services/Db/compose.yaml`, `services/Db/Dockerfile`, `services/Db/.env.example` | `quadlets/db.container`, `quadlets/db-data.volume` |
| **api** | `services/Api/Dockerfile`, `services/Api/compose.yaml`, `services/Api/.env.example`, `services/Api/src/config.py` | `quadlets/api.container` |
| **webclient** | `services/WebClient/Dockerfile`, `services/WebClient/compose.yaml`, `services/WebClient/nginx.conf`, `services/WebClient/.env.production` | `quadlets/webclient.container` |
| **rosbridge** | `services/RosBridge/Dockerfile`, `services/RosBridge/compose.yaml`, `services/RosBridge/config/` | `quadlets/rosbridge.container` |
| **proxy** | `services/Proxy/Dockerfile`, `services/Proxy/nginx.container.conf` | `quadlets/proxy.container` |
| **(red)** | — | `quadlets/labs-remoto.network` |

Además, revisar `quadlets/deploy.sh` si cambió algún Dockerfile o contexto de build.

## Qué verificar y sincronizar

Para cada servicio indicado:

1. **Imagen**: si el Dockerfile cambió de imagen base, verificar que el quadlet la refleje (solo db usa imagen directa; los demás usan `localhost/labs-remoto/<servicio>`)
2. **Puertos**: si cambiaron puertos expuestos (`EXPOSE` en Dockerfile o `ports` en compose), actualizar `PublishPort` en el quadlet
3. **Variables de entorno**: si se agregaron/eliminaron variables (revisar `config.py`, `.env.example`, `compose.yaml`), actualizar comentarios en el quadlet y verificar que el `EnvironmentFile` sea correcto
4. **Volúmenes**: si cambiaron montajes o paths internos
5. **Comando**: si cambió el `CMD`/`ENTRYPOINT` del Dockerfile, actualizar `Exec` en el quadlet
6. **Dependencias entre servicios**: si un servicio ahora depende de otro (o dejó de depender), actualizar `Requires=` y `After=` en el quadlet
7. **Red/Alias**: verificar que `NetworkAlias` coincida con el hostname esperado por otros servicios
8. **Healthchecks**: si cambiaron en el Dockerfile o compose
9. **deploy.sh**: si cambió un Dockerfile path, contexto de build, o se agregó/eliminó un servicio, actualizar el array `IMAGES` y `SERVICES` en `deploy.sh`

## Reglas

- **No modificar** la configuración fuente (Dockerfiles, compose, etc.) — solo los quadlets
- **Preservar comentarios** existentes en los quadlets
- **Mantener la convención de tags**: `localhost/labs-remoto/<servicio>`
- **Env files** van en `/etc/containers/env/` en el servidor
- **Puertos de servicios internos** (api, webclient) NO se publican — solo accesibles via proxy
- **Puertos de db y rosbridge** se publican solo en `127.0.0.1`
- **El proxy** es el único que publica el puerto 80 al exterior
- Si hay cambios relevantes, actualizar también los READMEs (`quadlets/README.md` y `quadlets/README.es.md`)

## Formato de salida

Después de sincronizar, mostrar un resumen conciso:
- Qué archivos se modificaron y qué cambió en cada uno
- Si no hubo cambios necesarios, indicarlo
