# Bridges WebSocket para ROS 2 con Autenticación
> Evaluación de alternativas a rosbridge con soporte de auth

---

## Pregunta

¿Existe un adaptador WS para ROS 2 (como rosbridge) que soporte autenticación?

**Respuesta corta: no.** No hay un bridge WebSocket para ROS 2 con auth integrada que sea drop-in para rosbridge.

---

## Alternativas evaluadas

| Solución | Auth | ¿Drop-in para rosbridge? | Notas |
|---|---|---|---|
| **rosbridge** | Ninguna | N/A | Tuvo `rosauth` en ROS 1 (MAC SHA-512), fue removido en ROS 2. Los maintainers consideran auth "fuera del scope" |
| **Foxglove Bridge** | Solo TLS server-side | No (protocolo Foxglove, no rosbridge) | Cifra el canal pero no verifica al cliente. Soporta whitelisting de topics por regex |
| **eProsima Integration Service** | JWT (HS256) + TLS | No (protocolo propio, compilar desde source) | El único con auth real sobre WS. Pero es un framework pesado con protocolo propio, no compatible con roslibjs |
| **Robofleet** | IP + Google Sign-in | No (usa FlatBuffers) | Proyecto académico (UT Austin), diseñado para visualización de flotas, no bridging general |
| **Transitive Robotics** | JWT + mTLS | No (plataforma completa, usa MQTT internamente) | Producto comercial/open-source. Introduce dependencia de cloud |

---

## eProsima Integration Service — el más cercano

Es un framework de bridging de protocolos de eProsima (creadores de Fast DDS). Puede bridgear ROS 2 (vía DDS) a WebSocket con JWT.

```yaml
systems:
  websocket_server:
    type: websocket_server
    port: 443
    cert: /path/to/cert.crt
    key: /path/to/key.pem
    authentication:
      policies:
        - secret: "your-jwt-secret"
          algo: HS256
          rules:
            example: "*regex*"
  ros2:
    type: ros2
topics:
  your_topic:
    type: "std_msgs/msg/String"
    route: ros2_to_ws
```

### Por qué no es práctico para nuestro caso

- Protocolo WS propio, no compatible con rosbridge/roslibjs — hay que reescribir clientes
- Requiere compilar desde source (C++)
- Pesado de operar y mantener
- Costo de migración alto para una ganancia que se puede obtener de otra forma

---

## El patrón estándar: auth por fuera del bridge

La comunidad ROS resuelve esto poniendo un **gateway autenticado delante del bridge**, no buscando un bridge con auth.

Nuestra arquitectura actual ya implementa este patrón:

```
[Usuario] ──WS + JWT──► [API FastAPI] ──WS (interna)──► [rosbridge]
                              ↑                               ↑
                         valida auth                    solo accesible
                         por mensaje                    desde intranet
                         (JWT usuario +                 (nginx restringe
                          JWT robot_access)              /rosbridge/ a intranet)
```

La API actúa como gateway autenticado. rosbridge nunca está expuesto a clientes no confiables.

### Variantes del patrón

**A) nginx con `auth_request`** — valida un token en el HTTP upgrade antes de proxear a rosbridge. Limitación: solo valida al abrir la conexión, no por mensaje.

**B) Gateway a nivel de aplicación (nuestro caso)** — la API valida cada mensaje WS antes de reenviarlo a rosbridge. Es el más seguro porque la validación es por mensaje, no solo por conexión.

**C) Proxy WS custom** — un proceso ligero que acepta WS con JWT, valida, y reenvía a rosbridge. Más simple que la opción B pero sin lógica de dominio.

---

## Conexión con la decisión de MQTT

Este análisis refuerza la elección de MQTT como transporte:

- **No existe** un rosbridge con auth para ROS 2
- El patrón de "auth por fuera del bridge" funciona, pero agrega una capa extra
- MQTT **tiene auth, TLS y QoS nativos** en el protocolo — no necesita un gateway extra
- Mosquitto como broker **fue diseñado** para manejar múltiples clientes autenticados

Con MQTT, la autenticación vive en el transporte mismo, no hace falta construirla alrededor.

---

## rosbridge: historial de auth

Para contexto, rosbridge tuvo auth en ROS 1 vía el paquete `rosauth`:

- Esquema MAC: `sha512(secret + client_UA + dest + rand + time + level + timeEnd)`
- El cliente enviaba un op `auth` al conectarse
- El servidor validaba con el nodo `rosauth`
- **Removido en ROS 2** — nunca fue portado
- Issues conocidos incluso cuando existía: [#434](https://github.com/RobotWebTools/rosbridge_suite/issues/434) (auth roto con Autobahn), [#459](https://github.com/RobotWebTools/rosbridge_suite/issues/459) ("Unknown operation: auth")
- [Issue #569](https://github.com/RobotWebTools/rosbridge_suite/issues/569) propone control de acceso granular por usuario — sigue abierto y sin implementar

---

## Referencias

- [rosbridge_suite (GitHub)](https://github.com/RobotWebTools/rosbridge_suite)
- [rosauth (GitHub, ROS 1, deprecado)](https://github.com/GT-RAIL/rosauth)
- [Foxglove Bridge (GitHub)](https://github.com/foxglove/ros-foxglove-bridge)
- [eProsima Integration Service (GitHub)](https://github.com/eProsima/Integration-Service)
- [eProsima WebSocket System Handle (docs)](https://integration-service.docs.eprosima.com/en/latest/user_manual/systemhandle/websocket_sh.html)
- [Robofleet (GitHub)](https://github.com/ut-amrl/robofleet_server)
- [Transitive Robotics](https://transitiverobotics.com/)
