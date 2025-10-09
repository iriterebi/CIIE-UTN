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
2. EDITA el archivo 'config/.env' y ajusta la variable 'USB_PORT' con el puerto correcto de tu Arduino.

# Pasos para encontrar el puerto en Linux (Raspberry Pi/Ubuntu):

1. Desconecta el Arduino y ejecuta:
```bash
ls /dev/ttyA* /dev/ttyU*
```
2. Conecta el Arduino y ejecuta de nuevo el comando. El puerto nuevo que aparece (ej: /dev/ttyACM0) es el que debes usar.

3. Modifica el contenido de 'config/.env' (Ejemplo):
```bash
USB_PORT=/dev/ttyACM0
```

## 🔨 Build de la imagen

```bash
./lazy_start.sh
```


## Correr el agente
Ya dentro del docker corre el comando:
```bash
./ros2_serial_agent/start.sh
```

## Al terminar el proceso, en el tab que dice curl, hay que pegar el comando 
```bash
sudo curl https://control.inorbit.ai/liftoff/WklSDRtViJNzWRPN | sh
```
# SI TE PIDE UN ROS_DOMAIN_ID, PONE 42


## Testing:
Hardcodear datos en el ros2 topic para probar conectividad con InOrbit:
```bash
ros2 topic pub /inorbit/custom_data std_msgs/String "{data: 'instruccion=23'}" -r 10
```

Tambien podemos ver los logs del agente haciendo:
```bash
tail -f ~/.inorbit/local/inorbit.log
```
```bash
tail -f ~/.inorbit/local/inorbit_agent.log
```