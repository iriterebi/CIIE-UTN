# ROS 2 en Docker (con acceso a USB)

Este proyecto corre ROS 2 Humble dentro de un contenedor Docker en la Raspberry Pi o en cualquier host con soporte ARM64.  
El contenedor puede acceder a un dispositivo **USB** (por ejemplo, un microcontrolador conectado al puerto serie).

---

## 🚀 Requisitos

- Raspberry Pi (ARM64) o PC con Docker instalado  
- Un dispositivo USB conectado (ejemplo: `/dev/ttyUSB0`)  
- Configurar variables de entorno: copiar archivo config/example.env, renombrar como config/.env y cambiar datos relevantes
---

## 🔨 Build de la imagen

```bash
./build.sh
```
## ▶️ Correr el contenedor

Si tenes configurado el USB_PORT en config/.env tomara ese, sino montara el docker sin port

```bash
./run.sh
```
