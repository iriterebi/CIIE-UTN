# ROS 2 en Docker (con acceso a USB)

Este proyecto corre ROS 2 Humble dentro de un contenedor Docker en la Raspberry Pi o en cualquier host con soporte ARM64.  
El contenedor puede acceder a un dispositivo **USB** (por ejemplo, un microcontrolador conectado al puerto serie).

---

## 🚀 Requisitos

- Raspberry Pi (ARM64) o PC con Docker instalado  
- Un dispositivo USB conectado (ejemplo: `/dev/ttyUSB0`)  
- Configurar variables de entorno: copiar archivo config/example.env, renombrar como config/.env y cambiar datos relevantes
---
## CONFIGURACIÓN INICIAL
Modificar Variables de Entorno: Antes de empezar, debes asegurarte de que el contenedor sepa qué puerto USB debe utilizar en el sistema anfitrión (host).
1. COPIA el archivo de ejemplo a la ubicación real:
```bash
cp .env.example config/.env
```
EDITA el archivo 'config/.env' y ajusta la variable 'USB_PORT' con el puerto correcto de tu Arduino.

Pasos para encontrar el puerto en Linux (Raspberry Pi/Ubuntu):

Desconecta el Arduino.

Ejecuta:
```bash
ls /dev/ttyA* /dev/ttyU*
```
Conecta el Arduino.

Ejecuta de nuevo el comando. El puerto nuevo que aparece (ej: /dev/ttyACM0) es el que debes usar.

Contenido de 'config/.env' (Ejemplo):
```bash
USB_PORT=/dev/ttyACM0
```

## 🔨 Build de la imagen

```bash
./build.sh
```
## ▶️ Correr el contenedor

Si tenes configurado el USB_PORT en config/.env tomara ese, sino montara el docker sin port

```bash
./run.sh
```

