# Red y Despliegue — nginx, DDS y topología de comunicación

## Índice

- [Visión General](#visión-general)
- [Topología de Red](#topología-de-red)
- [nginx como Proxy Principal](#nginx-como-proxy-principal)
  - [Por qué nginx y no HAProxy](#por-qué-nginx-y-no-haproxy)
  - [Instalación nativa (no Docker)](#instalación-nativa-no-docker)
  - [Ruteo de servicios](#ruteo-de-servicios)
  - [WebSocket — manejo de timeouts](#websocket--manejo-de-timeouts)
  - [Restricción de rutas internas](#restricción-de-rutas-internas)
  - [TLS](#tls)
- [RosBridge como puerta de entrada para los robots](#rosbridge-como-puerta-de-entrada-para-los-robots)
  - [Por qué las Pis no pueden usar rclpy directamente](#por-qué-las-pis-no-pueden-usar-rclpy-directamente)
  - [Flujo de conexión a través de nginx](#flujo-de-conexión-a-través-de-nginx)
- [Migración futura: API a rclpy](#migración-futura-api-a-rclpy)
- [Arquitectura final](#arquitectura-final)

---

## Visión General

El servidor de despliegue tiene un único punto de entrada: **nginx**, instalado directamente en el host (no en Docker). Todos los demás servicios (API, DB, RosBridge, WebClient) corren en contenedores Docker.

nginx cumple tres funciones:
1. **Reverse proxy** — rutea tráfico HTTP y WebSocket a los servicios internos
2. **Servidor de archivos** — sirve la SPA de Vue 3
3. **TLS termination** — maneja certificados SSL

Los robots (RaspberryPi) son dispositivos **externos al servidor**, conectados por intranet. No están en la red Docker ni en la misma red DDS. Se comunican con el servidor a través de nginx.

---

## Topología de Red

```
                          INTRANET
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   ┌──────────────┐                                      │
    │   │ RaspberryPi A│──┐                                   │
    │   └──────────────┘  │                                   │
    │                     │                                   │
    │   ┌──────────────┐  │    HTTPS/WSS                      │
    │   │ RaspberryPi B│──┼──────────────►┌──────────────┐    │
    │   └──────────────┘  │               │              │    │
    │                     │               │    nginx     │    │
    │   ┌──────────────┐  │               │   (host)     │    │
    │   │ RaspberryPi C│──┘               │              │    │
    │   └──────────────┘                  └──────┬───────┘    │
    │                                            │            │
    │                    ┌───────────────────────────────┐     │
    │   INTERNET         │        Docker (ciie-test)     │     │
    │       │            │                               │     │
    │       └───────────►│  ┌─────┐ ┌────┐ ┌──────────┐ │     │
    │                    │  │ API │ │ DB │ │ RosBridge│ │     │
    │                    │  └─────┘ └────┘ └──────────┘ │     │
    │                    │                               │     │
    │                    └───────────────────────────────┘     │
    └─────────────────────────────────────────────────────────┘
```

Puntos clave:
- nginx está en el host, fuera de Docker
- Las Pis están en la intranet, fuera del servidor
- Los servicios Docker se comunican entre sí por la red `ciie-test`
- nginx es el único componente accesible tanto desde internet como desde la intranet

---

## nginx como Proxy Principal

### Por qué nginx y no HAProxy

Se evaluaron ambas opciones. nginx es la elección correcta para este proyecto por:

| Criterio | nginx | HAProxy |
|----------|-------|---------|
| **Servir SPA** | Nativo — `try_files` para Vue | No sirve archivos, requiere otro servicio |
| **WebSocket proxy** | Soportado con headers upgrade | Soportado, detección automática |
| **Ruteo por path** | `location` blocks — natural | ACLs + `use_backend` — más verboso |
| **TLS + Let's Encrypt** | `certbot --nginx` integrado | Requiere concatenar cert+key, renovación manual |
| **Balanceo avanzado** | Básico | Excelente (no lo necesitamos ahora) |

HAProxy sería mejor con múltiples instancias de la API, balanceo L4, o circuit breaking avanzado. Con un solo servidor y la necesidad de servir archivos estáticos, nginx hace todo en un solo componente.

### Instalación nativa (no Docker)

nginx se instala directamente en el host, no en un contenedor. Razones:

- Es la puerta de entrada al servidor — gestionar TLS, certificados y red es más simple sin la capa extra de Docker
- Necesita acceso directo a los puertos 80/443 del host
- La configuración de `certbot` y renovación automática es más directa en el host
- Todos los demás servicios sí corren en Docker — nginx es la excepción

### Ruteo de servicios

nginx rutea el tráfico según el path del request:

| Path | Destino | Tipo | Origen |
|------|---------|------|--------|
| `/` | Archivos estáticos (SPA Vue) | HTTP | Internet |
| `/auth/*` | API (FastAPI) | HTTP | Internet |
| `/admin/*` | API (FastAPI) | HTTP | Internet |
| `/user/robot/*` | API (FastAPI) | HTTP + **WebSocket** | Internet |
| `/m2m/robot/*` | API (FastAPI) | HTTP | Intranet (solo Pis) |
| RosBridge (WS) | RosBridge (:9090) | **WebSocket** | Intranet (solo Pis) |

Las rutas de la API se proxean al contenedor FastAPI. La SPA se sirve directamente desde el filesystem del host (copiada en el build).

### WebSocket — manejo de timeouts

nginx cierra conexiones inactivas a los **60 segundos** por defecto. Para WebSockets esto es un problema — una sesión de usuario o la conexión de una Pi pueden estar inactivas por minutos.

Solución: aumentar `proxy_read_timeout` y `proxy_send_timeout` en las locations de WebSocket. Complementar con **ping/pong a nivel aplicación** para detectar conexiones muertas (más robusto que solo el timeout).

### Restricción de rutas internas

Las rutas `/m2m/*` son internas — solo las Pis deben acceder. nginx puede restringir por IP:

```nginx
location /m2m {
    proxy_pass http://api;
    allow 10.0.0.0/8;
    allow 172.16.0.0/12;
    allow 192.168.0.0/16;
    deny all;
}
```

El acceso a RosBridge también se restringe de la misma forma — solo las Pis de la intranet deben poder conectarse.

### TLS

Se usa Let's Encrypt con el plugin de nginx para certificados SSL:

```bash
certbot --nginx -d dominio.edu
```

nginx redirige todo el tráfico HTTP (puerto 80) a HTTPS (puerto 443). Tanto el tráfico de usuarios (internet) como el de las Pis (intranet) pasa por TLS.

---

## RosBridge como puerta de entrada para los robots

### Por qué las Pis no pueden usar rclpy directamente

La primera intuición es migrar las Pis a `rclpy` (ROS 2 nativo) para eliminar el intermediario de RosBridge. Sin embargo, la topología de red lo impide:

**DDS (el transporte de ROS 2) requiere visibilidad de red directa entre nodos.** Usa multicast UDP para descubrimiento automático y conexiones peer-to-peer para datos. Las Pis están en la intranet, fuera de la red Docker del servidor, fuera de la red DDS.

Opciones para conectar DDS a través de redes separadas:

| Opción | Descripción | Problema |
|--------|-------------|----------|
| **DDS Discovery Server** | Reemplaza multicast por servidor centralizado (unicast) | Requiere abrir puertos DDS (11811 + rango dinámico), no pasa por nginx (es tráfico UDP/TCP directo, no HTTP) |
| **Zenoh bridge** | Protocolo que bridgea DDS sobre TCP/QUIC | Agrega complejidad significativa, componente extra |
| **RosBridge vía nginx** | Las Pis se conectan al WebSocket de RosBridge a través de nginx | Funciona con la infraestructura actual, sin puertos extra |

**RosBridge es la herramienta correcta para este caso.** Existe exactamente para dar acceso a ROS 2 desde fuera de la red DDS mediante un protocolo web estándar (WebSocket). nginx sabe proxear WebSocket, así que las Pis se conectan a RosBridge a través del mismo punto de entrada que todo lo demás.

### Flujo de conexión a través de nginx

```
RaspberryPi (intranet)
    │
    ├── POST https://servidor/m2m/robot/register      → nginx → API
    ├── POST https://servidor/m2m/robot/handshake      → nginx → API
    │   (recibe JWT + topic base)
    │
    └── WSS  wss://servidor/rosbridge                  → nginx → RosBridge (:9090)
        (suscribe a /robot/r<base32>/command)
        (publica a /robot/r<base32>/response, /status)
```

Todo el tráfico de la Pi pasa por nginx en el puerto 443 (TLS). No se necesitan puertos adicionales abiertos.

---

## Migración futura: API a rclpy

Si en el futuro la API migra de cliente WebSocket de RosBridge a nodo ROS 2 nativo (rclpy), la situación es distinta:

- La API **sí está en la misma red Docker** que RosBridge y los nodos ROS
- DDS puede funcionar dentro de la red Docker con `network_mode: host` o configurando discovery explícitamente
- La API se convertiría en un nodo ROS 2 que publica/suscribe directamente en DDS, sin pasar por RosBridge

```
Actual:    API ──WS──► RosBridge ──► DDS
Futuro:    API ──rclpy──► DDS directamente
```

Esto **no afecta a nginx ni a las Pis**:
- nginx sigue proxyeando HTTP/WS de usuarios hacia la API
- Las Pis siguen conectándose a RosBridge vía nginx (RosBridge se mantiene para ellas)
- RosBridge sigue existiendo como puente para cualquier cliente fuera de la red DDS

La migración de la API a rclpy es un cambio interno al servidor — la interfaz externa (nginx) no cambia.

---

## Arquitectura final

```
                         INTERNET                    INTRANET
                            │                           │
                            │                    ┌──────┴───────┐
                            │                    │ RaspberryPi  │
                            │                    │  (×N robots) │
                            │                    └──────┬───────┘
                            │                           │
                            ▼                           ▼
                    ┌───────────────────────────────────────┐
                    │              nginx (host)              │
                    │                                       │
                    │  :443 ──► /           → SPA (Vue 3)   │
                    │           /auth/*     → API (:8000)   │
                    │           /admin/*    → API (:8000)   │
                    │           /user/*     → API (:8000)   │  ← WS upgrade
                    │           /m2m/*      → API (:8000)   │  ← solo intranet
                    │           /rosbridge  → RosBridge     │  ← solo intranet, WS
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────┴────────────────────────┐
                    │           Docker (ciie-test)           │
                    │                                       │
                    │  ┌─────────┐  ┌──────┐  ┌──────────┐ │
                    │  │   API   │  │  DB  │  │ RosBridge│ │
                    │  │ FastAPI │  │ PG   │  │  :9090   │ │
                    │  │  :8000  │  │:5432 │  │          │ │
                    │  └────┬────┘  └──────┘  └────┬─────┘ │
                    │       │          WS          │       │
                    │       └──────────────────────┘       │
                    │        (API → RosBridge, o rclpy     │
                    │         directo en el futuro)        │
                    └──────────────────────────────────────┘
```

Resumen de decisiones:
- **nginx nativo en el host** — punto de entrada único, TLS, SPA, proxy
- **RosBridge se mantiene** — puente necesario para las Pis que están fuera de la red DDS
- **Las Pis pasan por nginx** — registro, handshake y conexión RosBridge, todo por el mismo puerto 443
- **La API puede migrar a rclpy** independientemente — es un cambio interno, no afecta la interfaz externa
- **No se necesitan puertos extra** — todo el tráfico entra por nginx (80 → 301, 443)
