# rosbridge vs mqtt_client: Adaptadores de Transporte ROS 2
> Clarificación conceptual — ambos cumplen el mismo rol

---

## Concepto clave

Tanto rosbridge como mqtt_client son **traductores de protocolo** entre el mundo ROS/DDS y un protocolo WAN-friendly. Adaptan la capa de transporte para que clientes que no hablan DDS puedan comunicarse con el grafo ROS local.

```
rosbridge:    [cliente WS]   ←JSON/WS→    [rosbridge]   ←DDS→  [nodos ROS]
mqtt_client:  [cliente MQTT] ←string/MQTT→ [mqtt_client] ←DDS→  [nodos ROS]
```

Funcionalmente hacen lo mismo: traducen mensajes entre un cliente que no habla DDS y el grafo ROS local.

---

## Diferencia: el protocolo de transporte

La diferencia no está en lo que hacen, sino en las propiedades del protocolo que exponen:

| Propiedad | rosbridge (WebSocket) | mqtt_client (MQTT) |
|---|---|---|
| Autenticación | No | Sí (usuario/password, certificados) |
| Cifrado (TLS) | No nativo | Sí (nativo) |
| QoS / garantía de entrega | No | Sí (3 niveles: at-most-once, at-least-once, exactly-once) |
| Buffering ante desconexión | No — mensajes se pierden | Sí — el broker retiene mensajes |
| Diseñado para múltiples clientes | No — pensado para un cliente web | Sí — Mosquitto maneja miles de clientes |
| Formato de payload | JSON (verbose) | String plano o binario (eficiente) |
| Overhead de protocolo | Alto (JSON + protocolo rosbridge) | Bajo (headers mínimos) |

---

## Implicación para Labs Remoto

rosbridge fue pensado para **un cliente web hablando con un grafo ROS local**. Lo estamos usando como broker centralizado para múltiples robots — un uso para el que no fue diseñado.

MQTT (con Mosquitto como broker) es exactamente el patrón correcto para nuestro caso: múltiples dispositivos remotos comunicándose con un servidor central a través de un broker diseñado para eso.

El adaptador en la Pi (sea rosbridge o mqtt_client o un nodo custom) cumple el mismo rol: traducir entre DDS local y el protocolo WAN. Lo que cambia es la calidad del transporte.
