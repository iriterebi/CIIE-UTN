# Arquitectura

```
------------------------------------------------------------------------
|                                                                      |
| [micro core] ──strategy── [ROS 2 / serial / mock]                    |
|     │            (local)                                             |
|     ├────────strategy── [WS / mqtt / http pull-push loop]  ──────────|───→ API
|     │            (remoto)                                            |
|     └──────── [Unix Socket] ◄────────────────────────────────────────|───→ [cli]
|                                                                      |
------------------------------------------------------------------------
```

- **micro core** (asyncio, main thread): enrutador puro — mueve mensajes en formato interno entre adapters, no transforma datos. Cada adapter traduce entre su protocolo externo y el formato interno. Conecta dos strategies y el socket de gestión
- **strategy local** (ROS 2 por defecto): módulo de conexión con DDS. Daemon thread con `rclpy.spin()`. Intercambiable (serial directo, mock, etc.)
- **strategy remoto** (WS por defecto): módulo de conexión con la API. Corre en asyncio del core. Intercambiable (alternativa futura: MQTT)
- **Unix Socket**: interfaz de gestión (start/stop/status). Solo gestión, no datos
- **cli**: proceso separado, se conecta al core a través del socket. Habilita que el core corra como daemon (systemd, etc.)

---

# Plan de Refactor

este es un plan general para el refactor del subporyecto, para movernos a la nueva arquitectura. Lo haremos en 2 grandes bloques

## 1. Estructura

Cambiaremos al estructura del código a la nueva arquitectura, procurando mantener la funcionalidad actual. Para ello replantearmoes lo que tenemos:

- Strategy Interno: @controller/robot/ tiene la impleemntación de la comuniación interna, tanto serial como mock.
- Strategy Externo: @controller/rosbrdige/ tiene la implementación para conectarse con rosbridge, la trabajaremos para llevarla la strategy que necesitamos

Como no tenemos "micro core", esto será lo nuevo, para esta etapa conectará los strategies y escuchará el Unix Socket (y nada más)


## 2. Cli v1.1

Crearemos un Cli muy simple que hable con el sistema, este solo pedirá estatus del sistema y el "micro core" debe responderle. Esta etapa está para plantear el cli

## 3. Cli v1.2

Agregaremos un comando switch: el "strategy interno" mock tiene un loop que envía telemetría mock, este switch permitirá habilitar/deshabilitar ese loop.
Esta etapa es para plantear el funcionamiento de control del cli y el micro core

## 4. Strategy Selection

Acá agregaremos la posibilidad de seleccionar los strategies, por ahora solo tenemos uno remoto y dos locales, pero es suficiente para plantear el mecanismo de selección.

### 4.1

Agregaremos nueva información de status que será mostrada por el cli cuando se pida:

```
Estado de conexión
- strategy remoto: [CONECTADO/DESCONECTADO] [<strategy seleccionado>|<NONE>]
- strategy local: [CONECTADO/DESCONECTADO] [<strategy seleccionado>|<NONE>]
```

### 4.2.1 boot: seleeción de los strategies al inicio
se selecciona según config (.env)

### 4.2.2 loop: seleeción en vuelo
Se selecciona en vuelo con el cli. Para ello hay que agregar dos subcomandos al cli, uno para cambiar el strategy remoto y otro para el local. El cambio implica "apagar" el strategy (deben tener una subrutinna start, stop, y pause), desconectar el enrutado (romper el pipe), Conectar el nuevo strategy y start



## 5. WS

Crearemos el strategy remoto para el WS

NOTA: Cada strategy debe pedir sus propias credenciales, ya que las credenciales provistas por la API son diferentes según el mecanismo de comunicación.

