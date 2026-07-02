# CLAUDE.md — Proxy

## Descripción General

Configuración de nginx como reverse proxy principal del servidor de despliegue. nginx es el único componente instalado directamente en el host (no en Docker) — es el punto de entrada único para todo el tráfico del sistema.

## Estructura

```
Proxy/
├── nginx.conf      # Configuración de nginx para producción
├── CLAUDE.md
├── README.md
└── README.es.md
```

No tiene Dockerfile, compose.yaml ni Makefile — nginx se instala y gestiona directamente en el host con `systemctl` y los archivos de configuración en `/etc/nginx/`.

## Instalación

```bash
sudo cp nginx.conf /etc/nginx/sites-available/labs-remoto
sudo ln -s /etc/nginx/sites-available/labs-remoto /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

TLS con Let's Encrypt:
```bash
sudo certbot --nginx -d <DOMINIO>
```

## Responsabilidades de nginx

1. **Servir la SPA** — archivos estáticos de Vue 3 en `/var/www/labs-remoto`, con `try_files` para SPA fallback
2. **Reverse proxy a la API** — rutas `/api/*`, `/ws/*` y `/m2m/*` hacia FastAPI (`127.0.0.1:8000`)
3. **TLS termination** — certificados SSL vía Let's Encrypt / certbot
4. **Control de acceso** — la ruta `/m2m/*` (registro, handshake y WS de robots) está restringida a IPs de intranet

## Mapa de Rutas

| Path | Destino | Tipo | Acceso |
|------|---------|------|--------|
| `/` | SPA (`/var/www/labs-remoto`) | HTTP | Público |
| `/api/*` | API (:8000), quita prefijo `/api` | HTTP | Público |
| `/ws/*` | API (:8000), quita prefijo `/ws` | WebSocket | Público |
| `/m2m/*` | API (:8000) | HTTP + WebSocket (`/m2m/robot/connect`) | Solo intranet |

## Upstreams

Los servicios Docker deben publicar puertos solo en `127.0.0.1` para que no sean accesibles directamente desde la red — solo nginx los expone:

- `127.0.0.1:8000` → API (FastAPI)

## WebSocket — Timeouts

- `/ws/*` (usuario↔API): `proxy_read_timeout 3600s` (1 hora)
- `/m2m/*` (Pi↔API, `/m2m/robot/connect`): `proxy_read_timeout 86400s` (24 horas)

Los timeouts largos evitan que nginx corte conexiones WebSocket inactivas (default: 60s). Se complementan con ping/pong a nivel aplicación.

## Restricción de Intranet

La ruta `/m2m/*` usa `allow`/`deny` para restringir acceso a rangos de IP privados:

```nginx
allow 10.0.0.0/8;
allow 172.16.0.0/12;
allow 192.168.0.0/16;
allow 127.0.0.1;
deny all;
```

## Despliegue de la SPA

Los archivos estáticos de Vue 3 se copian manualmente al host:

```bash
cd ../WebClient && npm ci && npm run build   # desde services/Proxy/
sudo cp -r dist/* /var/www/labs-remoto/
```

## Por qué nginx no está en Docker

- Gestionar TLS y certificados es más simple en el host
- Acceso directo a puertos 80/443
- certbot se integra nativamente
- Es la excepción — todos los demás servicios sí corren en Docker

## Operaciones Comunes

```bash
sudo nginx -t                      # Validar configuración
sudo systemctl reload nginx        # Aplicar cambios sin downtime
sudo systemctl restart nginx       # Reiniciar
sudo systemctl status nginx        # Ver estado
sudo tail -f /var/log/nginx/*.log  # Seguir logs
```
