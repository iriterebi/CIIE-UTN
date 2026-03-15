# Herramientas Avanzadas de ROS 2 — tf2, URDF/Xacro, Launch Files y Mensajes Estándar

## Índice

- [Concepto de Robot en el Sistema](#concepto-de-robot-en-el-sistema)
  - [Servos: nodos vs subtópicos](#servos-nodos-vs-subtópicos)
  - [Recomendación para el brazo de 7 DOF](#recomendación-para-el-brazo-de-7-dof)
- [Mensajes Estándar de ROS 2](#mensajes-estándar-de-ros-2)
  - [std_msgs — Tipos primitivos y utilidades](#std_msgs--tipos-primitivos-y-utilidades)
  - [geometry_msgs — Primitivas geométricas](#geometry_msgs--primitivas-geométricas)
  - [sensor_msgs — Datos de sensores](#sensor_msgs--datos-de-sensores)
  - [nav_msgs — Navegación](#nav_msgs--navegación)
  - [trajectory_msgs — Trayectorias articulares](#trajectory_msgs--trayectorias-articulares)
  - [visualization_msgs — Visualización en RViz](#visualization_msgs--visualización-en-rviz)
  - [diagnostic_msgs — Diagnóstico](#diagnostic_msgs--diagnóstico)
  - [shape_msgs — Formas 3D](#shape_msgs--formas-3d)
  - [stereo_msgs — Visión estéreo](#stereo_msgs--visión-estéreo)
  - [Mensajes relevantes para el proyecto](#mensajes-relevantes-para-el-proyecto)
- [JSON-RPC vs Mensajes ROS Nativos](#json-rpc-vs-mensajes-ros-nativos)
  - [Dónde sí tiene sentido JSON-RPC](#dónde-sí-tiene-sentido-json-rpc)
  - [Dónde no tiene sentido](#dónde-no-tiene-sentido)
- [JointState y su diferencia con Status](#jointstate-y-su-diferencia-con-status)
- [Agrupación de Robots y Dispositivos](#agrupación-de-robots-y-dispositivos)
  - [Namespaces (agrupación lógica)](#namespaces-agrupación-lógica)
  - [tf2 (agrupación espacial)](#tf2-agrupación-espacial)
  - [URDF/Xacro (agrupación mecánica)](#urdfxacro-agrupación-mecánica)
  - [Launch files (agrupación de deployment)](#launch-files-agrupación-de-deployment)
  - [Ejemplo: brazo + cámara de tracking](#ejemplo-brazo--cámara-de-tracking)
- [tf2 — El Árbol de Transformadas](#tf2--el-árbol-de-transformadas)
  - [El problema que resuelve](#el-problema-que-resuelve)
  - [Estructura del árbol](#estructura-del-árbol)
  - [Tipos de transforms](#tipos-de-transforms)
  - [Cómo se usa](#cómo-se-usa)
  - [Buffer temporal](#buffer-temporal)
  - [Reglas del árbol](#reglas-del-árbol)
- [URDF/Xacro — Descripción del Robot](#urdfxacro--descripción-del-robot)
  - [Links y Joints](#links-y-joints)
  - [Tipos de joints](#tipos-de-joints)
  - [Geometrías disponibles](#geometrías-disponibles)
  - [Ejemplo completo: brazo de 2 eslabones](#ejemplo-completo-brazo-de-2-eslabones)
  - [Xacro — Macros para URDF](#xacro--macros-para-urdf)
  - [Cómo se usa el URDF en runtime](#cómo-se-usa-el-urdf-en-runtime)
- [Launch Files — Orquestación de Nodos](#launch-files--orquestación-de-nodos)
  - [Estructura básica](#estructura-básica)
  - [Parámetros](#parámetros)
  - [Argumentos de launch](#argumentos-de-launch)
  - [Remappings](#remappings)
  - [Composición](#composición)
  - [Acciones condicionales](#acciones-condicionales)
  - [Event handlers](#event-handlers)
  - [Ejemplo completo: laboratorio con brazo + cámara](#ejemplo-completo-laboratorio-con-brazo--cámara)
- [Cómo se Conectan tf2, URDF y Launch Files](#cómo-se-conectan-tf2-urdf-y-launch-files)
- [Aplicación al Proyecto: Dónde Iría Cada Herramienta](#aplicación-al-proyecto-dónde-iría-cada-herramienta)
  - [URDF — Vive en el repositorio, se consume en varios lugares](#urdf--vive-en-el-repositorio-se-consume-en-varios-lugares)
  - [robot_state_publisher — En la Pi](#robot_state_publisher--en-la-pi)
  - [tf2 — Distribuido, no centralizado](#tf2--distribuido-no-centralizado)
  - [Launch files — Uno por contexto de ejecución](#launch-files--uno-por-contexto-de-ejecución)
  - [Diagrama de distribución](#diagrama-de-distribución)
- [Requisito: ROS 2 Instalado](#requisito-ros-2-instalado)
  - [Alternativas sin ROS](#alternativas-sin-ros)

---

## Concepto de Robot en el Sistema

### Servos: nodos vs subtópicos

El brazo robótico tiene 7 servos (base, cuerpo, hombro, brazo, antebrazo_1, antebrazo_2, mano), todos en un solo Arduino conectado por un solo puerto serial. No hay paralelismo real — los comandos van secuenciales por el mismo cable.

Esto descarta **un nodo ROS por servo**: 7 nodos competirían por escribir al mismo serial, necesitarían un mutex o un nodo coordinador, y terminarían recreando lo que ya hace el Arduino.

Las opciones reales son:

**A) Robot como unidad atómica (lo que se tiene hoy)**

```
/robot/r<id>/command   →  {"method": "move_arm", "params": {"base": 90, "hombro": 45}}
/robot/r<id>/response  ←  {"result": {"status": "ok"}}
/robot/r<id>/status    ←  {"method": "status.update", "params": {...}}
```

El robot es una caja negra. Simple, refleja la realidad física (un serial, un Arduino).

**B) Subtópicos por servo (dentro del mismo nodo)**

```
/robot/r<id>/command           →  comandos generales (execute_sequence, etc.)
/robot/r<id>/servo/base        ←  estado del servo base (ángulo actual)
/robot/r<id>/joint_states      ←  mensaje JointState estándar de ROS
```

Un solo nodo maneja el serial, pero publica estado granular por servo. Mejor observabilidad, compatible con herramientas ROS (RViz, MoveIt).

### Recomendación para el brazo de 7 DOF

Mantener el robot como unidad atómica para **comandos** (mover un brazo requiere coordinar múltiples articulaciones simultáneamente — mover servo por servo puede causar colisiones del brazo consigo mismo), pero publicar **estado granular** por servo:

```
/robot/r<id>/command        →  comandos (poses o trayectorias completas)
/robot/r<id>/response       ←  respuestas a comandos
/robot/r<id>/joint_states   ←  sensor_msgs/JointState (7 servos, ángulos actuales)
/robot/r<id>/status         ←  heartbeat / metadatos operativos del robot
```

Esto requiere que el Arduino reporte posiciones actuales, lo cual el firmware actual no hace.

---

## Mensajes Estándar de ROS 2

ROS 2 incluye **117 mensajes** distribuidos en **9 paquetes** dentro de `common_interfaces`. Repositorio: https://github.com/ros2/common_interfaces

### std_msgs — Tipos primitivos y utilidades

30 mensajes. Wrappers básicos para publicar valores sueltos. Rara vez se usan directamente en sistemas maduros.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `Bool` | Un booleano | Señal on/off de un sensor |
| `Byte` | Un byte (0-255) | Dato crudo de hardware |
| `Char` | Un carácter | — |
| `Float32` | Float 32 bits | Lectura de temperatura simple |
| `Float64` | Float 64 bits | Lectura de un encoder |
| `Int8/16/32/64` | Enteros con signo | Contadores, IDs |
| `UInt8/16/32/64` | Enteros sin signo | Contadores, máscaras de bits |
| `String` | Cadena de texto | **Lo que usa el proyecto hoy** — JSON-RPC dentro de un string |
| `Empty` | Mensaje vacío (sin campos) | Trigger/señal: "empezá a grabar" |
| `Header` | `stamp` + `frame_id` | No se publica solo — se embebe en otros mensajes para timestamp y frame de referencia |
| `ColorRGBA` | Color con alfa (4 floats) | Color de un marker en RViz |
| `*MultiArray` | Array N-dimensional de primitivos (8 tipos) | Matrices, imágenes custom, datos tabulares |
| `MultiArrayDimension` | Dimensión de un MultiArray | Helper interno de MultiArray |
| `MultiArrayLayout` | Layout de un MultiArray | Helper interno de MultiArray |

### geometry_msgs — Primitivas geométricas

31 mensajes. El paquete más usado en robótica. Posición, orientación y movimiento.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `Point` | Posición 3D (x, y, z) | Ubicación de un objeto detectado |
| `Point32` | Igual pero en float32 (más liviano) | Vértices de una nube de puntos |
| `PointStamped` | Point + Header | "El objeto está acá, medido a las 14:30 en frame `camera`" |
| `Vector3` | Vector 3D (x, y, z) | Velocidad lineal, fuerza |
| `Vector3Stamped` | Vector3 + Header | Lectura de acelerómetro con timestamp |
| `Quaternion` | Orientación como cuaternión (x,y,z,w) | Orientación del robot en el espacio |
| `QuaternionStamped` | Quaternion + Header | Salida de un IMU |
| `Pose` | Position + Orientation (Point + Quaternion) | "El robot está en (1,2,0) mirando al norte" |
| `PoseStamped` | Pose + Header | Goal de navegación: "andá a esta pose" |
| `PoseArray` | Lista de Poses | Partículas de un filtro de localización |
| `PoseWithCovariance` | Pose + matriz 6x6 de incertidumbre | Estimación de posición con confianza |
| `PoseWithCovarianceStamped` | Anterior + Header | Salida típica de AMCL (localización) |
| `Twist` | Velocidad lineal + angular (2x Vector3) | "Mové a 0.5 m/s y girá a 0.1 rad/s" |
| `TwistStamped` | Twist + Header | Comando de velocidad con timestamp |
| `TwistWithCovariance` | Twist + covarianza | Odometría con incertidumbre |
| `TwistWithCovarianceStamped` | Anterior + Header | Publicación de odometría de ruedas |
| `Accel` | Aceleración lineal + angular | Perfil de aceleración de un controlador |
| `AccelStamped` | Accel + Header | Lectura de acelerómetro |
| `AccelWithCovariance` | Accel + covarianza | Aceleración estimada con incertidumbre |
| `AccelWithCovarianceStamped` | Anterior + Header | Fusión de sensores IMU |
| `Wrench` | Fuerza + torque (2x Vector3) | Lectura de un sensor de fuerza/torque |
| `WrenchStamped` | Wrench + Header | Control de fuerza en un brazo robótico |
| `Transform` | Translación + rotación | Relación entre dos frames |
| `TransformStamped` | Transform + Header + `child_frame_id` | **tf2**: "el frame `base_link` está acá respecto a `odom`" |
| `Inertia` | Masa + centro de masa + tensor de inercia | Modelo dinámico de un eslabón del brazo |
| `InertiaStamped` | Inertia + Header | Inercia variable (carga cambiante) |
| `Polygon` | Lista de Point32 | Footprint del robot para navegación |
| `PolygonStamped` | Polygon + Header | "Este es mi contorno en el frame `base_link`" |
| `PolygonInstance` | Polygon + id | Instancia individual de un polígono detectado |
| `PolygonInstanceStamped` | Anterior + Header | Detección de objetos por contorno |
| `VelocityStamped` | Twist (linear + angular) + Header | Similar a TwistStamped, agregado recientemente |

### sensor_msgs — Datos de sensores

27 mensajes. Todo lo que un sensor puede producir. **`JointState` vive acá**.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| **`JointState`** | **Nombre, posición, velocidad y esfuerzo de articulaciones** | **Brazo robótico: 7 servos con sus ángulos** |
| `MultiDOFJointState` | Igual pero para articulaciones con 6 DOF | Base de un drone (posición + orientación) |
| `Imu` | Acelerómetro + giroscopio + orientación | MPU6050 en la Raspberry Pi |
| `Image` | Imagen cruda (ancho, alto, encoding, data) | Cámara RGB |
| `CompressedImage` | Imagen comprimida (JPEG, PNG) | Streaming de video por red |
| `CameraInfo` | Parámetros intrínsecos/extrínsecos de cámara | Calibración para visión 3D |
| `LaserScan` | Barrido de LIDAR 2D (rangos + ángulos) | RPLIDAR, Hokuyo |
| `MultiEchoLaserScan` | Laser scan con múltiples ecos por rayo | LIDAR multi-eco |
| `LaserEcho` | Múltiples rangos de un rayo | Helper de MultiEchoLaserScan |
| `PointCloud` | Nube de puntos (lista de Point32 + canales) | Legacy — LIDAR 3D |
| `PointCloud2` | Nube de puntos v2 (más eficiente, campos custom) | Velodyne, Intel RealSense depth |
| `PointField` | Descriptor de un campo en PointCloud2 | "El campo `rgb` empieza en byte 12, es float32" |
| `Range` | Distancia de un sensor ultrasónico/IR | HC-SR04 en Arduino |
| `NavSatFix` | Posición GPS (lat, lon, alt + covarianza) | Módulo GPS |
| `NavSatStatus` | Estado del GPS (fix type, servicio) | "GPS con fix 3D, usando SBAS" |
| `BatteryState` | Voltaje, corriente, carga, capacidad, temperatura | Batería del robot |
| `Temperature` | Temperatura en Celsius | Sensor de temperatura ambiente |
| `RelativeHumidity` | Humedad relativa (0-1) | Sensor DHT22 |
| `FluidPressure` | Presión en Pascales | Barómetro |
| `Illuminance` | Iluminancia en Lux | Sensor de luz ambiente |
| `MagneticField` | Campo magnético 3D (Tesla) | Magnetómetro/brújula |
| `Joy` | Estado de un joystick (axes + buttons) | Control manual del robot con gamepad |
| `JoyFeedback` | Feedback a joystick (LEDs, rumble) | Vibrar el control cuando el robot choca |
| `JoyFeedbackArray` | Lista de JoyFeedback | Múltiples efectos simultáneos |
| `RegionOfInterest` | Rectángulo (x, y, ancho, alto) | ROI en una imagen para tracking |
| `ChannelFloat32` | Canal de datos con nombre | Helper legacy de PointCloud |
| `TimeReference` | Timestamp de un reloj externo (GPS time) | Sincronización de reloj |

### nav_msgs — Navegación

8 mensajes. Para robots que se mueven en un entorno.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `Odometry` | Pose + Twist + covarianzas | "Estoy en (3,2) moviéndome a 0.5 m/s" — fusión de encoders |
| `Path` | Lista de PoseStamped | Trayectoria planificada por Nav2 |
| `OccupancyGrid` | Mapa 2D de ocupación (celdas 0-100) | Mapa generado por SLAM |
| `MapMetaData` | Resolución, ancho, alto, origen del mapa | Metadata de un OccupancyGrid |
| `GridCells` | Lista de celdas (puntos) | Visualización de celdas obstáculo en RViz |
| `Trajectory` | Secuencia de TrajectoryPoints con timestamps | Planificación temporal de movimiento |
| `TrajectoryPoint` | Pose + Twist + Accel en un instante | Un punto de una trayectoria planificada |
| `Goals` | Lista de Poses objetivo | Múltiples waypoints de navegación |

### trajectory_msgs — Trayectorias articulares

4 mensajes. **Directamente relevante para el brazo robótico del proyecto.**

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| **`JointTrajectory`** | **Header + nombres de joints + lista de puntos** | **"Mové el brazo por esta secuencia de poses en estos tiempos"** |
| **`JointTrajectoryPoint`** | **Posiciones, velocidades, aceleraciones, esfuerzos + tiempo** | **Un punto de la trayectoria: "en t=0.5s, base a 90°, hombro a 45°"** |
| `MultiDOFJointTrajectory` | Igual pero para joints de 6 DOF | Trayectoria de una base flotante (drone) |
| `MultiDOFJointTrajectoryPoint` | Punto de la anterior | Un waypoint de drone con pose + twist + accel |

### visualization_msgs — Visualización en RViz

12 mensajes. Para dibujar cosas en RViz.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `Marker` | Forma 3D (esfera, cubo, flecha, mesh, texto...) | Dibujar una flecha de velocidad sobre el robot |
| `MarkerArray` | Lista de Markers | Dibujar obstáculos detectados |
| `ImageMarker` | Marker 2D sobre una imagen | Dibujar un círculo en el feed de cámara |
| `InteractiveMarker` | Marker que el usuario puede arrastrar en RViz | Mover un waypoint con el mouse |
| `InteractiveMarkerControl` | Cómo se manipula un InteractiveMarker | "Este marker se puede rotar en el eje Z" |
| `InteractiveMarkerFeedback` | Evento del usuario manipulando un marker | "El usuario movió el marker a (3,2,0)" |
| `InteractiveMarkerInit` | Estado inicial de markers interactivos | Sincronización al conectar RViz |
| `InteractiveMarkerPose` | Pose actualizada de un marker | Update de posición durante drag |
| `InteractiveMarkerUpdate` | Update incremental de markers | Agregar/eliminar/mover markers |
| `MenuEntry` | Entrada de menú contextual de un marker | "Click derecho → Eliminar waypoint" |
| `MeshFile` | Referencia a archivo de mesh (STL, DAE) | Cargar modelo 3D del robot |
| `UVCoordinate` | Coordenada de textura UV | Mapeo de textura sobre un mesh |

### diagnostic_msgs — Diagnóstico

3 mensajes. Para reportar salud del sistema.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `DiagnosticArray` | Lista de DiagnosticStatus + Header | Reporte periódico de salud de todos los nodos |
| `DiagnosticStatus` | Nivel (OK/WARN/ERROR) + nombre + mensaje + key-values | "Motor izquierdo: WARN — temperatura 85°C" |
| `KeyValue` | Par clave-valor (strings) | Helper de DiagnosticStatus |

### shape_msgs — Formas 3D

4 mensajes. Para representar objetos sólidos.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `SolidPrimitive` | Cubo, esfera, cilindro o cono (tipo + dimensiones) | Volumen de colisión de un eslabón del brazo |
| `Mesh` | Malla de triángulos + vértices | Modelo de colisión detallado |
| `MeshTriangle` | Tres índices de vértices | Un triángulo del mesh |
| `Plane` | Plano (coeficientes a,b,c,d) | Detección de superficies (mesa, piso) |

### stereo_msgs — Visión estéreo

1 mensaje.

| Mensaje | Descripción | Ejemplo de uso |
|---------|-------------|----------------|
| `DisparityImage` | Mapa de disparidad + parámetros de cámara | Profundidad calculada de un par estéreo |

### Mensajes relevantes para el proyecto

| Mensaje | Para qué se usaría |
|---------|-------------------|
| `sensor_msgs/JointState` | Publicar estado actual de los 7 servos (ángulos) |
| `trajectory_msgs/JointTrajectory` | Enviar trayectorias completas al brazo |
| `diagnostic_msgs/DiagnosticStatus` | Reemplazar el `/status` custom con algo estándar |
| `sensor_msgs/BatteryState` | Si la Pi tiene batería |
| `std_msgs/String` | Lo que se usa hoy (JSON-RPC como string) |

La migración natural: `String` con JSON-RPC → `JointTrajectory` para comandos + `JointState` para estado.

---

## JSON-RPC vs Mensajes ROS Nativos

### Dónde sí tiene sentido JSON-RPC

- **Usuario ↔ API** (WebSocket) — el frontend es un cliente web genérico, no sabe de ROS
- **Pi ↔ API para registro/handshake** (HTTP) — es REST, no pasa por ROS

### Dónde no tiene sentido

En la comunicación **API ↔ Pi vía ROS**. Hoy se hace:

```
API → serializar JSON-RPC → meter en std_msgs/String → rosbridge → Pi → deserializar JSON-RPC → ejecutar
```

Cuando se podría hacer:

```
API → publicar JointTrajectory → rosbridge → Pi → leer posiciones directamente
```

Con mensajes ROS tipados se elimina:

- Serialización/deserialización JSON en ambos extremos
- Validación manual de campos (el schema ya está en el `.msg`)
- Los códigos de error JSON-RPC — ROS tiene sus propios mecanismos (actions con feedback/result/status)
- El wrapping de meter un string JSON dentro de `msg.data`

Además, cualquier nodo ROS del ecosistema (RViz, MoveIt, nodo de seguridad) podría interactuar con el brazo sin un adaptador JSON-RPC custom.

---

## JointState y su diferencia con Status

`sensor_msgs/JointState` es un mensaje estándar de ROS:

```python
Header header          # timestamp
string[] name          # ["base", "hombro", "brazo", "antebrazo_1", ...]
float64[] position     # [1.57, 0.78, ...]   radianes
float64[] velocity     # opcional
float64[] effort       # opcional (torque/fuerza)
```

Es **el** estándar para describir el estado de articulaciones. Lo usan RViz, MoveIt, Gazebo, tf2.

Se separa de `status` porque son cosas conceptualmente distintas:

| | `joint_states` | `status` |
|---|---|---|
| **Qué describe** | Estado físico de las articulaciones | Estado operativo del robot |
| **Ejemplo** | "base está a 90°, hombro a 45°" | "online, mock=false, batería 80%" |
| **Frecuencia** | Alta (10-50 Hz para visualización fluida) | Baja (cada 5s) |
| **Consumidor** | Visualización 3D, cinemática, límites | Monitoreo, dashboard admin |
| **Tipo ROS** | `sensor_msgs/JointState` | Custom o `diagnostic_msgs/DiagnosticStatus` |

Si se mezclan en un solo topic: frecuencia incompatible y acoplamiento innecesario.

---

## Agrupación de Robots y Dispositivos

ROS no tiene un concepto formal de "grupo" — la agrupación es emergente de varias capas.

### Namespaces (agrupación lógica)

Cada dispositivo vive en un namespace. Se pueden anidar:

```
/lab1/brazo/joint_states          # el brazo
/lab1/brazo/command               # comandos al brazo
/lab1/camara/image_raw            # la cámara
/lab1/camara/camera_info          # calibración
```

`/lab1/` es el grupo. No existe como entidad — es convención de nombres. Cualquier nodo que quiera todo lo del lab1 se suscribe a `/lab1/#`.

### tf2 (agrupación espacial)

El árbol de transforms define la relación física entre cosas. Si la cámara está montada sobre el brazo:

```
world
 └── lab1/base_link
      └── lab1/brazo/link0
           └── ... (eslabones del brazo)
                └── lab1/brazo/end_effector
                     └── lab1/camara/optical_frame    ← cámara montada en el efector
```

Si la cámara es externa (cenital, para tracking):

```
world
 ├── lab1/brazo/base_link
 │    └── ... (eslabones)
 └── lab1/camara/optical_frame    ← cámara fija, hermana del brazo
```

tf2 permite preguntar "¿dónde está el end_effector respecto a la cámara?" sin importar cómo estén conectados.

### URDF/Xacro (agrupación mecánica)

El archivo URDF define qué es "un robot". Un brazo con cámara puede ser un URDF o dos URDFs compuestos con Xacro:

```xml
<!-- robot_completo.urdf.xacro (composición) -->
<xacro:include filename="brazo.urdf.xacro"/>
<xacro:include filename="camara.urdf.xacro"/>
<joint name="camera_to_effector" type="fixed">...</joint>
```

### Launch files (agrupación de deployment)

```python
# lab1.launch.py — esto "agrupa" brazo + cámara
def generate_launch_description():
    return LaunchDescription([
        Node(package='brazo_driver', namespace='lab1/brazo', ...),
        Node(package='camera_driver', namespace='lab1/camara', ...),
        Node(package='lab1_coordinator', namespace='lab1', ...),  # opcional
    ])
```

### Ejemplo: brazo + cámara de tracking

Lo más natural: **elementos separados, namespace compartido, sin nodo agrupador**:

```
/robot/r<id>/joint_states         ← brazo publica sus ángulos
/robot/r<id>/camera/image_raw     ← cámara publica video
/robot/r<id>/camera/camera_info   ← calibración
```

Cada uno tiene su nodo y su driver. El namespace los agrupa lógicamente. tf2 los conecta espacialmente. No se necesita un nodo coordinador a menos que haya lógica de coordinación explícita.

La idea general en ROS: **cada dispositivo físico = un nodo, la coordinación es otro nodo que consume y produce topics**. No hay "contenedores" de robots.

---

## tf2 — El Árbol de Transformadas

tf2 es el sistema que responde: **"¿dónde está X respecto a Y?"** en cualquier momento del tiempo.

### El problema que resuelve

Un robot tiene muchas partes y sensores, cada uno con su propio sistema de coordenadas (frame). El LIDAR mide respecto a sí mismo, la cámara ve respecto a su lente, las ruedas miden odometría respecto al punto de partida. Para hacer algo útil se necesita transformar datos entre frames.

Sin tf2 se hardcodean matrices de transformación entre cada par (N² relaciones). tf2 lo resuelve con un **árbol**: cada frame define su relación con su padre, y tf2 calcula cualquier transformación compuesta recorriendo el árbol.

### Estructura del árbol

```
map                          ← frame global (mapa del mundo)
 └── odom                    ← origen de odometría (acumula drift)
      └── base_link          ← centro del robot
           ├── laser_frame   ← dónde está el LIDAR
           ├── camera_frame  ← dónde está la cámara
           └── arm_base      ← base del brazo
                └── link1
                     └── link2
                          └── gripper
```

Cada flecha padre→hijo es una `TransformStamped`:

```python
# "laser_frame está a 10cm arriba y 5cm adelante de base_link"
transform:
  header:
    stamp: 1710200000.0
    frame_id: "base_link"        # padre
  child_frame_id: "laser_frame"  # hijo
  transform:
    translation: {x: 0.05, y: 0.0, z: 0.10}
    rotation: {x: 0, y: 0, z: 0, w: 1}  # sin rotación
```

### Tipos de transforms

**Estáticas** — no cambian nunca, se publican una vez:
```
base_link → laser_frame     (el LIDAR está atornillado)
base_link → camera_frame    (la cámara está fija en el chasis)
```

**Dinámicas** — cambian con el tiempo, se publican continuamente:
```
odom → base_link            (el robot se mueve)
arm_base → link1            (la articulación rota)
map → odom                  (la localización corrige el drift)
```

### Cómo se usa

**Publicar transforms** (broadcaster):

```python
from tf2_ros import TransformBroadcaster

br = TransformBroadcaster(node)
t = TransformStamped()
t.header.stamp = node.get_clock().now().to_msg()
t.header.frame_id = 'odom'
t.child_frame_id = 'base_link'
t.transform.translation.x = 1.5
t.transform.rotation.w = 1.0
br.sendTransform(t)
```

**Consultar transforms** (listener):

```python
from tf2_ros import Buffer, TransformListener

tf_buffer = Buffer()
tf_listener = TransformListener(tf_buffer, node)

# "¿dónde está el gripper respecto al mapa?"
transform = tf_buffer.lookup_transform('map', 'gripper', rclpy.time.Time())
# tf2 recorre: map → odom → base_link → arm_base → link1 → link2 → gripper
```

**Transformar datos entre frames**:

```python
# Punto detectado por la cámara → coordenadas del mapa
point_in_camera = PointStamped()
point_in_camera.header.frame_id = 'camera_frame'
point_in_camera.point.x = 2.0  # 2m adelante de la cámara

point_in_map = tf_buffer.transform(point_in_camera, 'map')
```

### Buffer temporal

tf2 guarda un historial (por defecto 10 segundos). Permite consultar transforms en el pasado:

```python
# "¿dónde estaba el robot hace 0.5 segundos?"
# Útil porque los datos del LIDAR tienen latencia
past_time = node.get_clock().now() - Duration(seconds=0.5)
transform = tf_buffer.lookup_transform('map', 'base_link', past_time)
```

### Reglas del árbol

- **Es un árbol, no un grafo** — cada frame tiene exactamente un padre (excepto la raíz)
- **No puede haber ciclos** — `A → B → C → A` es inválido
- **Un solo publisher por transform** — si dos nodos publican `odom → base_link`, hay conflicto
- **El frame raíz** no tiene padre. Por convención es `map` o `world`

---

## URDF/Xacro — Descripción del Robot

URDF (Unified Robot Description Format) es un XML que describe **qué es físicamente un robot**: sus partes, cómo se conectan, cómo se mueven, cómo se ven y cómo colisionan.

### Links y Joints

Un URDF tiene dos tipos de elementos:

**Links** — partes rígidas del robot (eslabones, chasis, sensores):

```xml
<link name="base_link">
  <!-- Lo que se ve en RViz/Gazebo -->
  <visual>
    <geometry>
      <box size="0.3 0.3 0.1"/>  <!-- caja de 30x30x10 cm -->
    </geometry>
    <material name="blue">
      <color rgba="0 0 0.8 1"/>
    </material>
  </visual>

  <!-- Lo que se usa para detectar colisiones (puede ser más simple que el visual) -->
  <collision>
    <geometry>
      <box size="0.3 0.3 0.1"/>
    </geometry>
  </collision>

  <!-- Propiedades físicas para simulación -->
  <inertial>
    <mass value="5.0"/>
    <inertia ixx="0.1" ixy="0" ixz="0" iyy="0.1" iyz="0" izz="0.1"/>
  </inertial>
</link>
```

**Joints** — conexiones entre links (articulaciones):

```xml
<joint name="hombro" type="revolute">
  <parent link="base_link"/>
  <child link="upper_arm"/>
  <origin xyz="0 0 0.1" rpy="0 0 0"/>  <!-- posición respecto al padre -->
  <axis xyz="0 0 1"/>                    <!-- eje de rotación: Z -->
  <limit lower="-1.57" upper="1.57"      <!-- límites en radianes -->
         velocity="1.0" effort="10.0"/>   <!-- velocidad y fuerza máxima -->
</joint>
```

### Tipos de joints

| Tipo | Movimiento | Ejemplo |
|------|-----------|---------|
| `fixed` | Ninguno — unión rígida | Cámara atornillada al chasis |
| `revolute` | Rotación con límites (min/max) | Articulación de un brazo (el caso del proyecto) |
| `continuous` | Rotación sin límites (360° infinito) | Rueda |
| `prismatic` | Traslación lineal con límites | Actuador lineal, elevador |
| `floating` | 6 DOF libres | Base de un drone |
| `planar` | Movimiento en un plano (2 DOF) | Mesa XY |

### Geometrías disponibles

```xml
<!-- Primitivas -->
<box size="largo ancho alto"/>
<cylinder radius="0.05" length="0.3"/>
<sphere radius="0.1"/>

<!-- Mesh externo (STL, DAE/Collada) -->
<mesh filename="package://mi_robot/meshes/base.stl" scale="0.001 0.001 0.001"/>
```

### Ejemplo completo: brazo de 2 eslabones

```xml
<?xml version="1.0"?>
<robot name="brazo_simple">

  <!-- Base fija -->
  <link name="base_link">
    <visual>
      <geometry><cylinder radius="0.05" length="0.02"/></geometry>
    </visual>
  </link>

  <!-- Primer eslabón -->
  <link name="link1">
    <visual>
      <geometry><box size="0.04 0.04 0.3"/></geometry>
      <origin xyz="0 0 0.15"/>
    </visual>
  </link>

  <joint name="joint1" type="revolute">
    <parent link="base_link"/>
    <child link="link1"/>
    <origin xyz="0 0 0.01"/>
    <axis xyz="0 1 0"/>
    <limit lower="-1.57" upper="1.57" velocity="1.0" effort="5.0"/>
  </joint>

  <!-- Segundo eslabón -->
  <link name="link2">
    <visual>
      <geometry><box size="0.04 0.04 0.25"/></geometry>
      <origin xyz="0 0 0.125"/>
    </visual>
  </link>

  <joint name="joint2" type="revolute">
    <parent link="link1"/>
    <child link="link2"/>
    <origin xyz="0 0 0.3"/>
    <axis xyz="0 1 0"/>
    <limit lower="-2.0" upper="2.0" velocity="1.5" effort="3.0"/>
  </joint>

</robot>
```

Esto genera el árbol de tf: `base_link → link1 → link2`

### Xacro — Macros para URDF

URDF puro es verbose y repetitivo. Xacro agrega programación al XML:

**Variables:**

```xml
<xacro:property name="largo_eslabon" value="0.3"/>
<box size="0.04 0.04 ${largo_eslabon}"/>
```

**Macros (funciones reutilizables):**

```xml
<xacro:macro name="eslabon" params="nombre largo color">
  <link name="${nombre}">
    <visual>
      <geometry><box size="0.04 0.04 ${largo}"/></geometry>
      <origin xyz="0 0 ${largo/2}"/>
      <material name="${color}"/>
    </visual>
  </link>
</xacro:macro>

<!-- Uso -->
<xacro:eslabon nombre="link1" largo="0.3" color="azul"/>
<xacro:eslabon nombre="link2" largo="0.25" color="rojo"/>
```

**Includes (composición):**

```xml
<xacro:include filename="brazo.urdf.xacro"/>
<xacro:include filename="camara.urdf.xacro"/>
<xacro:include filename="gripper.urdf.xacro"/>
```

**Condicionales y matemática:**

```xml
<xacro:if value="${usar_camara}">
  <xacro:include filename="camara.urdf.xacro"/>
</xacro:if>

<origin xyz="0 0 ${largo_total / 2 + offset}"/>
```

Xacro se compila a URDF puro antes de usarse: `xacro robot.urdf.xacro > robot.urdf`

### Cómo se usa el URDF en runtime

El URDF se carga en el **parameter server** como string y lo consumen:

- **`robot_state_publisher`** — lee el URDF + `JointState` → publica todas las transforms de tf2 automáticamente. Es el puente entre URDF y tf2
- **RViz** — renderiza el modelo 3D
- **MoveIt** — planifica trayectorias respetando límites y colisiones
- **Gazebo** — simula la física (usa `<inertial>` y `<collision>`)

```
URDF (estático) + JointState (dinámico) → robot_state_publisher → tf2 (transforms)
```

---

## Launch Files — Orquestación de Nodos

Los launch files definen **qué nodos arrancar, con qué parámetros, en qué namespace, y con qué remappings**. Son el equivalente a un `docker-compose.yaml` pero para nodos ROS.

En ROS 2 se escriben en Python (también XML o YAML, pero Python es el estándar).

### Estructura básica

```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='mi_paquete',
            executable='mi_nodo',
            name='nombre_custom',
            namespace='robot1',
            parameters=[{'param1': 42}],
            remappings=[('cmd_vel', 'velocidad')],
            output='screen',
        ),
    ])
```

### Parámetros

**Inline:**

```python
Node(
    package='camera_driver',
    executable='camera_node',
    parameters=[{
        'resolution': [640, 480],
        'fps': 30,
        'device': '/dev/video0',
    }],
)
```

**Desde archivo YAML:**

```yaml
# config/camera_params.yaml
camera_node:
  ros__parameters:
    resolution: [640, 480]
    fps: 30
    device: "/dev/video0"
```

```python
Node(
    package='camera_driver',
    executable='camera_node',
    parameters=['/ruta/a/camera_params.yaml'],
)
```

### Argumentos de launch

Permiten parametrizar el launch file desde la línea de comandos:

```python
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('robot_name', default_value='robot1'),
        DeclareLaunchArgument('use_sim', default_value='false'),

        Node(
            package='mi_driver',
            executable='driver_node',
            namespace=LaunchConfiguration('robot_name'),
            parameters=[{'simulation': LaunchConfiguration('use_sim')}],
        ),
    ])
```

```bash
ros2 launch mi_paquete mi_robot.launch.py robot_name:=brazo_lab1 use_sim:=true
```

### Remappings

Renombrar topics/services para conectar nodos que no fueron diseñados para trabajar juntos:

```python
Node(
    package='generic_camera',
    executable='camera_node',
    remappings=[
        ('image_raw', '/lab1/camara/image_raw'),
        ('camera_info', '/lab1/camara/camera_info'),
    ],
)
```

### Composición

Incluir otros launch files:

```python
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/ruta/a/brazo.launch.py'),
            launch_arguments={'namespace': 'lab1'}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/ruta/a/camera.launch.py'),
            launch_arguments={'device': '/dev/video0'}.items(),
        ),
        Node(package='mi_coordinador', executable='coordinador'),
    ])
```

### Acciones condicionales

```python
from launch.conditions import IfCondition, UnlessCondition

Node(
    package='gazebo_ros',
    executable='spawn_entity',
    condition=IfCondition(LaunchConfiguration('use_sim')),
),
Node(
    package='hardware_driver',
    executable='real_driver',
    condition=UnlessCondition(LaunchConfiguration('use_sim')),
),
```

### Event handlers

```python
from launch.actions import RegisterEventHandler, ExecuteProcess
from launch.event_handlers import OnProcessExit

def generate_launch_description():
    spawn = ExecuteProcess(cmd=['ros2', 'run', 'gazebo', 'spawn_robot'])

    return LaunchDescription([
        spawn,
        RegisterEventHandler(
            OnProcessExit(
                target_action=spawn,
                on_exit=[
                    Node(package='controller', executable='arm_controller'),
                ],
            )
        ),
    ])
```

### Ejemplo completo: laboratorio con brazo + cámara

```python
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    pkg = FindPackageShare('lab_bringup')

    return LaunchDescription([
        DeclareLaunchArgument('lab_id', default_value='lab1'),
        DeclareLaunchArgument('use_sim', default_value='false'),
        DeclareLaunchArgument('use_camera', default_value='true'),

        # Robot state publisher (carga URDF → publica tf2)
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=LaunchConfiguration('lab_id'),
            parameters=[{'robot_description': open('brazo.urdf').read()}],
        ),

        # Driver del brazo (o mock en simulación)
        Node(
            package='brazo_driver',
            executable='driver_node',
            namespace=LaunchConfiguration('lab_id'),
            parameters=[PathJoinSubstitution([pkg, 'config', 'brazo_params.yaml'])],
        ),

        # Cámara (opcional)
        Node(
            package='camera_driver',
            executable='camera_node',
            namespace=LaunchConfiguration('lab_id'),
            condition=IfCondition(LaunchConfiguration('use_camera')),
            remappings=[('image_raw', 'camera/image_raw')],
        ),

        # RViz para visualización
        Node(
            package='rviz2',
            executable='rviz2',
            condition=IfCondition(LaunchConfiguration('use_sim')),
            arguments=['-d', PathJoinSubstitution([pkg, 'rviz', 'lab.rviz'])],
        ),
    ])
```

```bash
ros2 launch lab_bringup lab_setup.launch.py lab_id:=lab1 use_camera:=true
ros2 launch lab_bringup lab_setup.launch.py lab_id:=lab2 use_sim:=true
```

---

## Cómo se Conectan tf2, URDF y Launch Files

```
URDF/Xacro                    Launch File                     tf2
(qué ES el robot)      →     (qué CORRE)              →     (dónde ESTÁ todo)
                                   │
                                   ├── robot_state_publisher
                                   │     lee URDF + JointState → publica tf2
                                   ├── driver del brazo
                                   │     publica JointState
                                   ├── driver de cámara
                                   │     publica Image
                                   └── rviz
                                         consume tf2 + URDF → renderiza 3D
```

El URDF describe la estructura, el launch file arranca los nodos que la operan, y tf2 mantiene el estado espacial en tiempo real. Los tres son declarativos en su definición pero producen un sistema dinámico en runtime.

---

## Aplicación al Proyecto: Dónde Iría Cada Herramienta

### URDF — Vive en el repositorio, se consume en varios lugares

El URDF es un archivo estático que describe el robot. No se "ejecuta" — se carga como dato. Lo necesitan:

- **La Pi** — para que `robot_state_publisher` publique tf2
- **El frontend** — para renderizar el brazo en 3D (si se llega a eso)
- **Cualquier nodo ROS** que necesite saber la geometría (MoveIt, RViz, simulador)

El URDF se publica como un **parámetro ROS** (`robot_description`) y cualquier nodo interesado lo lee. Es como un schema: se define una vez, lo comparten todos.

Si todos los brazos son el mismo modelo, el URDF es uno solo en el repo. Si hay variantes, se usa Xacro con parámetros.

### robot_state_publisher — En la Pi

Es el nodo que une URDF + `JointState` → tf2. Corre donde corren los drivers del robot:

```
Pi arranca →
  1. robot_state_publisher (carga URDF, escucha JointState, publica tf2)
  2. brazo_driver (lee serial del Arduino, publica JointState)
```

### tf2 — Distribuido, no centralizado

tf2 no es un servicio centralizado. Es pub/sub:

- Los **broadcasters** publican transforms en `/tf` y `/tf_static`
- Los **listeners** se suscriben y arman el árbol localmente

En este sistema:
- **La Pi** publica las transforms del brazo (vía `robot_state_publisher`)
- **Cualquier nodo** en la red puede escuchar `/tf` y consultar posiciones

### Launch files — Uno por contexto de ejecución

La Pi tendría su launch file y el servidor el suyo:

```python
# robot_bringup.launch.py — corre en la Pi
Node(package='robot_state_publisher', namespace=f'/robot/r{id}', ...)
Node(package='brazo_driver', namespace=f'/robot/r{id}', ...)
Node(package='camera_driver', namespace=f'/robot/r{id}', condition=IfCondition(...))

# server.launch.py — corre en el servidor
Node(package='rosbridge_server', ...)
```

### Diagrama de distribución

```
┌─── Servidor ──────────────────────┐     ┌─── Pi (por cada robot) ────────────┐
│                                   │     │                                     │
│  API (FastAPI)                    │     │  robot_state_publisher              │
│    - WebSocket con usuarios       │     │    - carga URDF                     │
│    - traduce comandos             │     │    - escucha JointState             │
│                                   │     │    - publica /tf                    │
│  RosBridge                        │     │                                     │
│    - puente WS ↔ ROS              │◄───►│  brazo_driver                       │
│    - topics van y vienen          │ red │    - serial ↔ Arduino               │
│                                   │     │    - publica JointState             │
│  (opcional) RViz / monitor        │     │    - escucha JointTrajectory        │
│    - consume tf2 + URDF           │     │                                     │
│    - visualiza estado             │     │  camera_driver (opcional)           │
│                                   │     │    - publica Image                  │
└───────────────────────────────────┘     │    - tf2 estática: cámara→brazo     │
                                          └─────────────────────────────────────┘

Archivos compartidos (en el repo):
  urdf/brazo_7dof.urdf.xacro    ← describe el robot
  launch/robot.launch.py        ← qué nodos arranca la Pi
  launch/server.launch.py       ← qué nodos arranca el servidor
  config/*.yaml                 ← parámetros de cada nodo
```

---

## Requisito: ROS 2 Instalado

URDF, tf2 y launch files son **componentes de ROS 2**, no herramientas independientes:

- **URDF**: el XML es legible sin ROS, pero `robot_state_publisher` (que lo interpreta y publica tf2) depende de `rclpy`, `tf2_ros`, `kdl_parser`
- **tf2**: los transforms se publican en `/tf` y `/tf_static` usando DDS como transporte. Sin ROS no hay ni transporte ni librerías
- **Launch files**: usan `launch_ros`, que importa `rclpy` para resolver paquetes, parámetros, namespaces

No son estándares abiertos que ROS adoptó — son invenciones de ROS que solo existen dentro de su ecosistema.

### Alternativas sin ROS

| Necesidad | Con ROS | Sin ROS |
|-----------|---------|---------|
| Describir el robot | URDF | El mismo XML, parseado con `urdf_parser_py` (pip, sin ROS) |
| Calcular cinemática | `robot_state_publisher` + KDL | `ikpy`, `roboticstoolbox-python` |
| Transforms | tf2 | Matrices con `numpy`/`scipy` |
| Orquestar procesos | Launch files | Script Python, `supervisord`, Docker Compose |

Es factible pero se pierde la integración: cada pieza se resuelve por separado y no se hablan entre sí automáticamente. El valor de ROS es ser un ecosistema donde todo encaja.

Para la Pi, agregar ROS 2 es usar una imagen base distinta (`ros:humble`) y reescribir el controller como nodos. El costo no es "instalar ROS" sino migrar la lógica actual.
