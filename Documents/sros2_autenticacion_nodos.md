# SROS2 — Autenticación y Seguridad entre Nodos ROS 2

## Índice

- [Qué es SROS2](#qué-es-sros2)
- [Cómo funciona](#cómo-funciona)
  - [Generar CA y certificados](#1-generar-ca-y-certificados)
  - [Definir permisos (control de acceso)](#2-definir-permisos-control-de-acceso)
  - [Activar con variables de entorno](#3-activar-con-variables-de-entorno)
  - [En código Python no cambia nada](#4-en-código-python-no-cambia-nada)
- [Aplicación al proyecto Labs Remoto](#aplicación-al-proyecto-labs-remoto)
  - [Por qué no aplica directamente](#por-qué-no-aplica-directamente)
  - [Seguridad actual del proyecto](#seguridad-actual-del-proyecto)
  - [Cuándo sí tendría sentido](#cuándo-sí-tendría-sentido)
- [Tradeoffs](#tradeoffs)
- [Riesgo residual y mitigaciones](#riesgo-residual-y-mitigaciones)

---

## Qué es SROS2

SROS2 (Secure ROS 2) es la capa de seguridad nativa de ROS 2. Usa las capacidades de seguridad de DDS (DDS-Security, parte del estándar) para proporcionar tres cosas:

| Capacidad | Qué hace | Analogía web |
|-----------|----------|-------------|
| **Autenticación** | Verifica la identidad de cada nodo con certificados X.509 | TLS mutuo (mTLS) |
| **Cifrado** | Encripta toda la comunicación DDS entre nodos | HTTPS |
| **Control de acceso** | Define qué nodos pueden publicar/suscribir a qué topics | ACLs / RBAC |

No es algo inventado por ROS — ROS 2 simplemente expone el plugin de seguridad de DDS con herramientas más amigables.

---

## Cómo funciona

### 1. Generar CA y certificados

Se crea un keystore (Autoridad Certificadora raíz) y se generan certificados por nodo:

```bash
# Crear el keystore (CA raíz)
ros2 security create_keystore /path/to/keystore

# Generar certificado + permisos para un nodo específico
ros2 security create_enclave /path/to/keystore /robot_a/controller
ros2 security create_enclave /path/to/keystore /robot_b/controller
```

Esto genera para cada nodo:
- `cert.pem` — certificado del nodo (firmado por la CA)
- `key.pem` — clave privada del nodo
- `permissions.xml` — qué puede hacer (publicar, suscribir, qué topics)
- `governance.xml` — políticas globales (¿cifrar todo? ¿permitir nodos sin cert?)

### 2. Definir permisos (control de acceso)

```xml
<!-- permissions.xml para el nodo controller del robot A -->
<permissions>
  <grant name="/robot_a/controller">
    <allow_rule>
      <publish>
        <topics>
          <topic>/robot/rabc123/response</topic>
          <topic>/robot/rabc123/status</topic>
        </topics>
      </publish>
      <subscribe>
        <topics>
          <topic>/robot/rabc123/command</topic>
        </topics>
      </subscribe>
    </allow_rule>
    <default>DENY</default>
  </grant>
</permissions>
```

Esto significa: el nodo `controller` del robot A **solo** puede publicar en sus topics de response/status y suscribirse a su topic de command. Si intenta leer el topic de otro robot → DDS lo rechaza.

### 3. Activar con variables de entorno

```bash
export ROS_SECURITY_KEYSTORE=/path/to/keystore
export ROS_SECURITY_ENABLE=true
export ROS_SECURITY_STRATEGY=Enforce  # o Permissive (para testing)
```

- Con `Enforce`, un nodo sin certificado válido **no puede comunicarse**
- Con `Permissive`, puede comunicarse pero se loguea un warning (útil para desarrollo)

### 4. En código Python no cambia nada

```python
import rclpy
from rclpy.node import Node

# El código del nodo es IDÉNTICO — la seguridad es transparente
# DDS maneja la autenticación/cifrado por debajo
node = Node('controller')
publisher = node.create_publisher(String, '/robot/rabc123/response', 10)
```

La seguridad es a nivel de DDS, no de aplicación. El código no necesita cambiar.

---

## Aplicación al proyecto Labs Remoto

### Por qué no aplica directamente

SROS2 protege la comunicación **entre nodos DDS**. En la arquitectura actual de Labs Remoto, la API y las RaspberryPi **no son nodos ROS 2** — son clientes WebSocket de rosbridge:

```
API ──WebSocket──► rosbridge ──DDS──► (nadie más por ahora)
Pi  ──WebSocket──► rosbridge ──┘
```

SROS2 no protege la conexión WebSocket entre la API/Pis y rosbridge. Protegería la comunicación DDS interna, que en este caso es solo entre rosbridge y los nodos ROS del otro equipo (si los hay).

### Seguridad actual del proyecto

La seguridad ya está resuelta a nivel de aplicación:

| Capa | Mecanismo actual | Protege |
|------|-----------------|---------|
| **Pi → API** | HTTP Basic + TLS (nginx) | Registro y handshake |
| **Pi → rosbridge** | TLS (nginx) + restricción IP intranet | Conexión WebSocket |
| **Usuario → API** | JWT + TLS | Sesiones y comandos |
| **API → rosbridge** | Red Docker interna (no expuesta) | Comunicación interna |
| **rosbridge (WS)** | Solo accesible desde intranet (nginx `deny all` fuera) | Acceso externo |

La restricción por IP de nginx (`allow 192.168.0.0/16; deny all;`) es lo que impide que alguien de internet se conecte directamente a rosbridge.

### Cuándo sí tendría sentido

1. **Si se migra la API a rclpy** (nodo ROS nativo) — la API sería un nodo DDS y SROS2 protegería su comunicación con otros nodos
2. **Si el equipo de ROS agrega más nodos** que se comunican entre sí por DDS — SROS2 aseguraría que un nodo comprometido no pueda leer/escribir topics de otros robots
3. **Si las Pis migraran a rclpy** y tuvieran visibilidad DDS directa (via Discovery Server o Zenoh) — pero la topología de red actual no lo permite (ver `red_y_despliegue.md`)

---

## Tradeoffs

| | A favor | En contra |
|---|---------|-----------|
| **SROS2** | Seguridad a nivel DDS, control granular por topic, cifrado nativo | Requiere PKI (gestión de certificados), solo protege nodos DDS (no WebSocket), complejidad operativa |
| **Esquema actual** | Funciona con la arquitectura existente, TLS + JWT + restricción IP, simple | No hay aislamiento entre topics a nivel DDS (si alguien accede a rosbridge, puede leer cualquier topic) |

---

## Riesgo residual y mitigaciones

El riesgo que SROS2 no cubre en la arquitectura actual: si una Pi se compromete (o alguien en la intranet se conecta al WebSocket de rosbridge a través de nginx), puede publicar en **cualquier topic**, no solo los suyos. rosbridge no valida qué topics puede usar cada conexión.

Mitigaciones posibles sin SROS2:

- **Validar en la API** que los comandos vengan del topic correcto para el robot autenticado
- **rosbridge con autenticación**: rosbridge tiene un parámetro `authenticate` experimental, pero no es robusto
- **Confiar en la restricción de intranet**: para el scope de un proyecto universitario, la restricción de red por IP es suficiente

**Conclusión**: SROS2 es la respuesta oficial de ROS 2 para autenticación entre nodos DDS nativos. En la arquitectura actual del proyecto (todo pasa por WebSocket/rosbridge), la seguridad se maneja a nivel aplicación con JWT + TLS + restricción de red, y es suficiente para el caso de uso.
