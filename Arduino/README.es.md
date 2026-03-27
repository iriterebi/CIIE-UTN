# /Arduino · Firmware del Robot

> **English**: [README.md](README.md)

Firmware nativo para el brazo robótico. Se ejecuta en una placa Arduino y controla 7 servos mediante señales PWM.

## Hardware

El brazo robótico consta de 7 servomotores, cada uno controlando una articulación diferente:

| Servo | Pin | Descripción |
|-------|-----|-------------|
| Base | 3 | Rota todo el brazo |
| Cuerpo | A0 | Controla el torso |
| Hombro | 6 | Articulación del hombro |
| Brazo | 9 | Movimiento del brazo superior |
| Antebrazo1 | 10 | Movimiento del antebrazo (eje 1) |
| Antebrazo2 | 5 | Movimiento del antebrazo (eje 2) |
| Mano | 11 | Pinza / mano |

## Funcionamiento

El firmware expone funciones de movimiento individuales por servo (`moverBase`, `moverMano`, etc.) y una función combinada `moverBrazo` que posiciona los 7 servos a la vez. Cada función recibe un ángulo (0–180°) y lo escribe al servo correspondiente.

El `loop()` actualmente ejecuta una secuencia de prueba simple, moviendo cada servo a 20° con un retardo de 1 segundo entre movimientos.

## Comunicación

En el sistema completo, la RaspberryPi envía comandos seriales al Arduino para controlar el brazo. La Pi recibe comandos de la API vía ROS/RosBridge y los traduce en instrucciones seriales para el Arduino.

```
[API] → [RosBridge/ROS] → [RaspberryPi] → [Serial] → [Arduino] → [Servos]
```

## Dependencias

- [Servo.h](https://www.arduino.cc/reference/en/libraries/servo/) — Librería estándar de Arduino para control de servos por PWM

## Herramientas

- [Arduino IDE](https://www.arduino.cc/en/software) — IDE gráfico oficial para escribir, compilar y subir sketches
- [Arduino CLI](https://arduino.github.io/arduino-cli/) — Herramienta de línea de comandos para compilar y subir sin el IDE

## Archivos

> `.ino` es el formato de archivo del [Arduino IDE](https://www.arduino.cc/en/software). Es esencialmente C/C++ — el IDE incluye automáticamente `Arduino.h` al compilar. Todo sketch requiere dos funciones: `setup()` (se ejecuta una vez al encender) y `loop()` (se ejecuta en bucle infinito).
