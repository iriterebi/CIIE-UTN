# CIIE Remote Labs

> [Read in English](./README.md)

Proyecto universitario para el control remoto de robots en laboratorios. Los usuarios interactúan a través de un frontend web, que se comunica con un backend Python (FastAPI) que hace de puente con los robots gestionados mediante ROS.

## Índice

- [Arquitectura](#arquitectura)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Stack Tecnológico](#stack-tecnológico)
- [Inicio Rápido](#inicio-rápido)
- [Convenciones](#convenciones)
- [Variables de Entorno](#variables-de-entorno)
- [Guía de Contribución](#-bienvenido-al-repositorio-de-ciie_remote_labs)
  - [Prerrequisitos](#-prerrequisitos-1)
  - [Configuración SSH](#1️⃣-configura-tu-clave-ssh-y-vincúlala-a-gitlab)
  - [Clonar el Repo](#2️⃣-clona-tu-repositorio)
  - [Ramas](#3️⃣-crea-una-nueva-rama-para-cada-cambio)
  - [Commits y Push](#4️⃣-haz-commits-y-sube-tu-código)
  - [Merge Requests](#5️⃣-crea-un-merge-request-mr)
  - [Buenas Prácticas para MRs](#buenas-prácticas-para-merge-requests-mrs)
- [Docker Deploy](#docker-deploy)
- [Configuración de Raspberry Pi](#configuración-de-raspberry-pi)

## Arquitectura

Para una descripción detallada de la arquitectura del sistema, flujos de comunicación, modelo de datos y despliegue, ver [Documents/arquitectura.md](./Documents/arquitectura.md).

```
[Frontend] → [API (FastAPI)] → [ROS] → [RaspberryPi] → [Arduino/Robot]
                  ↕
              [PostgreSQL]
```

## Estructura del Proyecto

| Directorio | Estado | Descripción |
|------------|--------|-------------|
| `Api/` | Activo (WIP) | Backend FastAPI — punto de entrada principal al sistema |
| `RaspberryPi/` | Activo | Controlador del lado del robot (comportamiento + comunicación) |
| `Db/` | Activo | Esquema PostgreSQL, migraciones (dbmate), datos semilla |
| `Arduino/` | Activo | Firmware del robot (control de brazo con 7 servos) |
| `ros_tryouts/` | Activo | Workspace ROS 2 para gestión de robots |
| `Documents/` | Activo | Documentación general del sistema |
| `WebClient/` | Activo | Frontend Vue 3 + TypeScript + PicoCSS |
| `RosBridge/` | Activo | rosbridge_suite — puente WebSocket/JSON entre API y ROS 2 |

## Stack Tecnológico

- **Backend**: Python 3.13.7+, FastAPI, SQLModel
- **Base de datos**: PostgreSQL 17.5
- **Autenticación**: JWT (HS256) + bcrypt
- **Frontend**: Vue 3, TypeScript, Vite, PicoCSS
- **Tiempo real**: WebSockets + ROS 2 vía RosBridge
- **Protocolo**: JSON-RPC 2.0 (comandos a robots)
- **Gestor de paquetes**: uv (workspace)
- **Despliegue**: Docker Compose
- **Migraciones**: dbmate

## Inicio Rápido

### Prerrequisitos

- Python 3.13.7+
- Gestor de paquetes uv
- Docker y Docker Compose

### 1. Crear la red Docker

```bash
docker network create ciie-test
```

### 2. Iniciar la base de datos

```bash
cd Db
make up_db.dev.detached    # Iniciar PostgreSQL en background
make migrate_db            # Ejecutar migraciones
make seed_apply            # Aplicar datos semilla
```

### 3. Iniciar la API

```bash
cd Api
make up_dev
```

### 4. Iniciar RosBridge

```bash
cd RosBridge
make build                # Construir imagen Docker (primera vez)
make up                   # Ejecutar rosbridge (foreground)
```

### 5. Iniciar el frontend

```bash
cd WebClient
npm install
npm run dev               # Servidor Vite en :5173
```

## Convenciones

- **Docker**: cada subproyecto se ejecuta vía Docker/Docker Compose
- **Modo demo**: todo el proyecto puede ejecutarse sin hardware físico (mock de RaspberryPi)
- **Makefiles**: cada subproyecto usa un Makefile como punto de entrada unificado para comandos
- **READMEs**: bilingües — `README.md` (inglés) y `README.es.md` (español)
- **Documentación**: escrita en español
- **Comentarios en código**: español o inglés

## Variables de Entorno

**Api** (requeridas):
- `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_URL`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ROSBRIDGE_URL` (ej: `ws://rosbridge:9090`)

**RaspberryPi** (`.env.defaults` tiene valores por defecto):
- `SERVER_URL`, `ROSBRIDGE_URL`, `ARDUINO_PORT`, `MOCK_ROBOT`, `CREATE_DEFAUL_METADATA`

Ver el README de cada subproyecto para más detalles.

---

## 🚀 Bienvenido al Repositorio de CIIE_Remote_Labs

Esta guía te llevará por los **primeros pasos** para comenzar a contribuir al proyecto. Aunque sea tu **primera vez usando GitLab o Git**, no te preocupes — te tenemos cubierto.

---

## 📌 Prerrequisitos

- Una cuenta de **GitLab** → https://gitlab.com
- **Git** instalado → https://git-scm.com/downloads
- Acceso a una terminal

---

## 1️⃣ Configura tu clave SSH y vincúlala a GitLab
Una clave SSH es un método de autenticación seguro para conectarse a servidores Git sin usar contraseña.

1. Genera una nueva clave SSH:
   Ve a tu terminal y ejecuta:
```bash
ssh-keygen -t ed25519 -C "tu_email@ejemplo.com"
```
   Luego presiona Enter para aceptar la ubicación por defecto.

2. Inicia el agente SSH y agrega tu clave:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

3. Copia la siguiente salida, será tu clave pública:
```bash
cat ~/.ssh/id_ed25519.pub
```
4. Ve a GitLab → Preferences → SSH key
5. Pega la clave, dale un nombre y haz clic en **add key**

## 2️⃣ Clona tu Repositorio
**¿Por qué clonar un repositorio?**
Clonar el repo a tu máquina local te permite trabajar offline y usar herramientas como un editor de código y terminal. Te da una copia completa del código donde puedes compilar, probar y hacer commits localmente antes de subirlos a GitLab.

1. Ve a tu repositorio y haz clic en el botón **code** (está en la esquina superior izquierda ;)
2. Copia el código SSH
3. En tu terminal, ve al directorio donde quieras tener tu repo y ejecuta:
```bash
git clone {{PEGARssh}}
```
4. Ahora puedes acceder a tu repo clonado como cualquier carpeta, usando cd.
5. Agrega tu nombre de usuario:
```bash
git config --global user.name "tu nombre"
```
6. Agrega tu email:
```bash
git config --global user.email "tu email"
```

## 3️⃣ Crea una Nueva Rama para Cada Cambio
**¿Por qué siempre crear una nueva rama?**
Trabajar en ramas separadas para cada tarea:
- Mantiene la rama principal limpia y estable
- Ayuda a organizar los cambios por propósito
- Facilita la revisión, prueba y reversión de features individuales
- Previene conflictos cuando varias personas trabajan en paralelo
- Cada rama se convierte en una unidad de trabajo autocontenida

Para crear una nueva rama, ve a tu terminal y ejecuta:
```bash
git checkout -b miNuevaRama
```
Nota: cuando creas una nueva rama, se copia la rama en la que estás actualmente.

## ¡FELICIDADES, YA ESTÁS LISTO PARA EMPEZAR A TRABAJAR!

## 4️⃣ Haz Commits y Sube tu Código
Después de cada cambio pequeño y significativo, deberías hacer un commit.
```bash
git add .
git commit -m "Explica claramente qué se cambió"
git push origin nombre-de-tu-rama
```

## 5️⃣ Crea un Merge Request (MR)
Una vez que hayas subido tu rama:
1. Ve a GitLab → haz clic en "Create merge request"
2. Completa:
   - Un título claro
   - Un mensaje descriptivo (qué cambió y por qué, contexto sobre la nueva feature, cómo probar, demos, imágenes, lo que sea)
3. Asigna al menos un reviewer
4. No hagas merge sin aprobación

Si es aprobado, tú (el autor) debes hacer el merge.
🛑 Aunque seas el reviewer del MR de otra persona, no hagas merge de su código.

## Buenas prácticas para Merge Requests (MRs)
✅ Un objetivo claro por MR
No mezcles cambios sin relación — un MR = un propósito.

✅ Commits pequeños y frecuentes
Facilita el seguimiento y la reversión si es necesario.

✅ Mensajes de commit descriptivos
Escribe mensajes que expliquen el qué y el por qué, ej:
Fix: prevenir crash cuando falta el username

✅ Escribe una descripción clara del MR
Explica qué hiciste, por qué importa, y cualquier contexto necesario para el reviewer.

✅ Asigna un reviewer
Siempre asigna a alguien para revisar antes de hacer merge. Nunca hagas self-merge sin revisión.

✅ Deja que el autor haga merge
Aunque hayas revisado, la persona que creó el MR debe ser quien haga el merge — esto evita confusión y mantiene la responsabilidad.

✅ Mantén la discusión respetuosa y constructiva
Las revisiones son un proceso colaborativo — todos trabajamos hacia el mismo objetivo. 💬🤝

---

## Docker Deploy

Ver [Docker-deploy.md](./Docker-deploy.md) para más información

---

### Configuración de Raspberry Pi:
NOTA: TANTO LA RASPY COMO EL LOCALDEV DEBEN ESTAR EN LA MISMA RED PARA FUNCIONAR.
1. Si estás usando hotspot, debes desactivar la configuración de proxy. Para eso, ejecuta los siguientes comandos (solo desactiva la configuración para la terminal activa):
```shell
unset http_proxy
unset https_proxy
unset ftp_proxy
unset HTTP_PROXY
unset HTTPS_PROXY
unset FTP_PROXY
```
2. Obtén la IP de red de tu computadora (no de la raspy):
```shell
ip addr
```
Busca en #3, bajo el nombre "wlp3s0", usa la IP nombrada bajo "inet" (hasta el /202) y agrega el puerto:
8080 para el sitio web, 3306 para interactuar con la db

3. Ejecuta el siguiente comando para verificar el localdev activo:
```shell
curl inet ip
```
IP priv Gabi: 172.22.144.1
