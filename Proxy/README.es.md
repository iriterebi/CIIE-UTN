# Proxy — nginx

[Read in English](README.md)

Reverse proxy principal del servidor de despliegue de Labs Remoto. nginx es el único componente instalado directamente en el host (no en Docker) — sirve como punto de entrada único para todo el tráfico.

## Responsabilidades

1. **Reverse proxy** — rutea tráfico HTTP y WebSocket a los servicios internos en Docker
2. **Servidor de archivos estáticos** — sirve la SPA de Vue 3
3. **TLS termination** — maneja certificados SSL (Let's Encrypt)
4. **Control de acceso** — restringe rutas internas (`/m2m`, `/rosbridge`) a IPs de la intranet

## Arquitectura

```
INTERNET ──► nginx (:443) ──► API (:8000)        [Docker]
INTRANET ──►               ──► RosBridge (:9090)  [Docker]
                            ──► SPA (archivos)     [filesystem del host]
```

- Los usuarios (internet) acceden a la SPA, API REST y WebSocket de usuario
- Las RaspberryPi (intranet) acceden a `/m2m/*` para registro/handshake y a `/rosbridge/` para comunicación ROS
- Los servicios Docker publican puertos solo en `127.0.0.1` — nginx es el único componente accesible externamente

## Mapa de Rutas

| Path | Destino | Tipo | Acceso |
|------|---------|------|--------|
| `/` | SPA (archivos estáticos Vue 3) | HTTP | Público |
| `/api/*` | API (:8000), quita el prefijo `/api` | HTTP | Público |
| `/ws/*` | API (:8000), WebSocket upgrade | WebSocket | Público |
| `/m2m/*` | API (:8000) | HTTP | Solo intranet |
| `/rosbridge/` | RosBridge (:9090), WebSocket upgrade | WebSocket | Solo intranet |

## Setup

### Instalar nginx

```bash
sudo apt install nginx
```

### Instalar configuración

```bash
sudo cp nginx.conf /etc/nginx/sites-available/labs-remoto
sudo ln -s /etc/nginx/sites-available/labs-remoto /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### TLS (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMINIO>
```

certbot modifica la configuración de nginx automáticamente y configura la renovación automática.

### Desplegar la SPA

```bash
cd ../WebClient && npm ci && npm run build
sudo mkdir -p /var/www/labs-remoto
sudo cp -r dist/* /var/www/labs-remoto/
```

## Por qué nginx no está en Docker

- Es la puerta de entrada al servidor — gestionar TLS, certificados y red es más simple sin la capa extra de Docker
- Necesita acceso directo a los puertos 80/443 del host
- La integración con certbot y la renovación automática funcionan de forma más natural en el host
- Todos los demás servicios sí corren en Docker — nginx es la excepción

## Por qué nginx y no HAProxy

Ver [Documents/red_y_despliegue.md](../Documents/red_y_despliegue.md) para la comparación completa. Resumen: nginx sirve la SPA nativamente, tiene ruteo por path más simple y se integra con certbot out of the box. Las ventajas de HAProxy (balanceo avanzado, circuit breaking) no son necesarias a esta escala.
