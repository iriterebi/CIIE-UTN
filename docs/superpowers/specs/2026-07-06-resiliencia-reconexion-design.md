# Diseño: resiliencia y reconexión Api ↔ RaspberryPi ↔ WebClient

- **Fecha**: 2026-07-06
- **Servicios**: `services/Api/`, `services/RaspberryPi/`, `services/WebClient/`
- **Estado**: aprobado, pendiente de plan de implementación

## Problema

El sistema tiene dos agujeros de resiliencia conocidos:

1. **Api ↔ RaspberryPi**: cuando la Pi se desconecta, la Api no se entera. El loop
   `async for message in websocket.iter_json()` en `services/Api/src/robot/routes/m2m.py`
   no tiene `try/except/finally`: si la conexión muere, la excepción se propaga sin manejar.
   `RobotConnectionRepository.discardRobotConnection` existe pero **nunca se invoca** (código
   muerto, confirmado por grep). La entrada del robot queda registrada como "viva" para
   siempre, y si hay un usuario con un pipe activo hacia ese robot, el pipe se queda colgado
   sin error ni cierre — nunca se entera de que el robot se fue.
2. **Api ↔ WebClient**: `services/WebClient/src/composables/useRobotSocket.ts` solo actualiza
   un estado local (`disconnected`/`error`) en `onclose`/`onerror`. No hay reintento de ningún
   tipo — el usuario debe recargar la página o volver a invocar `connect()` manualmente.

Adicionalmente, la detección de caída en ambas conexiones depende hoy pura y exclusivamente
del cierre "limpio" del socket (TCP FIN / frame de close WS). Para un brazo robótico físico
conectado por red local, un corte de cable, de wifi, o un corte de energía de la Raspberry Pi
no generan ningún cierre limpio — el socket queda colgado indefinidamente sin que nadie lo
note (salvo un keepalive TCP del SO, que por defecto puede tardar horas o no estar activo).

La reconexión Pi → Api (`services/RaspberryPi/controller/strategy/remote/ws_strategy.py`,
`WsStrategy`) ya funciona bien hoy: backoff exponencial 1s→30s, re-autenticación HTTP completa
en cada reconexión. **No se toca en este diseño.**

## Objetivo

Hacer que el sistema se recupere solo de desconexiones en ambos sentidos, sin intervención
manual del usuario ni reinicios manuales, distinguiendo entre:

- Caídas silenciosas (requieren heartbeat activo para detectarse).
- Cierres limpios/intencionales (ya detectables hoy, solo falta manejarlos).

## Fuera de alcance

- Persistir estado online/offline del robot en la base de datos. El estado vive en memoria en
  la Api (`RobotConnectionRepository`); esto no impide exponer un listado de robots con su
  estado actual vía un endpoint que lea ese estado en memoria.
- Bufferizar o reintentar comandos de usuario perdidos durante una desconexión del robot.
  Se rechazan de inmediato con error — encolar comandos para un brazo robótico físico que se
  ejecutarían tarde, fuera de contexto, es un riesgo que no vale la pena correr.
- Cambiar la lógica de reconexión ya existente en `WsStrategy` (Pi → Api). Ya cumple con lo
  necesario.

## Decisiones tomadas

### 1. Heartbeat de aplicación (Api↔Pi y Api↔Usuario)

- La Api es la única que inicia el ping en ambas conexiones que gestiona
  (`/m2m/robot/connect` y `/user/robot/send_command`). No es necesario que el heartbeat sea
  bidireccional: ni la Pi ni el WebClient necesitan iniciar sus propios pings.
- Formato: mensajes de control con un campo `type` reservado (ej. `{"type": "ping"}` /
  `{"type": "pong"}`), distinguibles del JSON-RPC 2.0 de comandos antes de intentar parsearlos
  como request — cero cambios al formato de comandos existente.
- Intervalo: ping cada 10s. Timeout: se considera muerta la conexión si no llega el pong
  correspondiente dentro de 15s (cubre ~1.5 ciclos, con margen). Valores configurables, no
  hardcodeados.
- Quién responde el ping:
  - Lado Pi: `WsStrategy` intercepta el ping y responde el pong directamente, sin exponerlo al
    `MicroCore` — transparente para el resto del sistema, igual que ya es transparente el
    reconnect actual.
  - Lado WebClient: `useRobotSocket.ts` intercepta el ping en `onmessage` y responde el pong,
    sin exponerlo al resto de la UI.
- **Watchdog del lado que recibe el ping** (necesario en ambos, Pi y WebClient): dado que el
  heartbeat es Api→cliente, cada cliente debe trackear el timestamp del último ping recibido.
  Si pasa más del umbral (~25s, cubriendo ~2 ciclos perdidos) sin recibir uno nuevo, el propio
  cliente se autodeclara desconectado — cierra el socket localmente aunque el SO todavía no lo
  haya notado — y dispara su flujo de reconexión. Esto es necesario porque si la Api completa
  (o su host) se vuelve inalcanzable, ningún paquete de cierre llega nunca; sin este watchdog,
  el cliente nunca se enteraría por sí solo.

### 2. Api ↔ Pi: fix del ciclo de vida, distinguiendo el motivo del cierre

`m2m.py` envuelve el loop `async for message in websocket.iter_json()` en `try/except/finally`.
Se distinguen dos motivos de cierre, con tratamiento distinto:

- **Cierre limpio** (`WebSocketDisconnect`, o el loop termina normalmente porque la Pi cerró
  el socket voluntariamente — ej. apagado graceful, `systemd stop`, redeploy): se interpreta
  como que **la Pi terminó la conexión a propósito**, un escenario irrecuperable desde el punto
  de vista de la conexión. En el `finally` se llama `discardRobotConnection` y el pipe
  asociado (si existe) se cierra **de inmediato**, terminando también la sesión del usuario.
- **Timeout de heartbeat** (la Api no recibe el pong a tiempo y decide unilateralmente que la
  conexión está muerta, sin que la Pi haya "avisado" nada): la Api cierra el WS explícitamente
  (`await websocket.close()`), lo que hace que el mismo loop `iter_json()` termine y caiga en
  el mismo `finally` — pero marcado como "muerte por timeout", no cierre limpio. Este es el
  único motivo que dispara la rama de "esperando reconexión" del pipe (sección siguiente).

Se reutiliza un único code path de limpieza (`finally`), diferenciado por una bandera/motivo,
en vez de duplicar lógica de cleanup para cada caso.

### 3. Pipe: estado de espera, solo para timeout de heartbeat

`RobotConnectionRepository` gana un "slot" por `robot_id` que puede contener una conexión
activa, o un marcador "esperando" con un `asyncio.Event` que se dispara cuando una nueva
`RobotConnection` se registra para ese mismo `robot_id` (la Pi reconectando trae su propio
backoff 1s→30s + re-auth completo, ya existente).

El lado robot del pipe corre un supervisor equivalente a:

```
try:
    await robot.connect()          # corre hasta que el robot lado termina
except RobotSideClosed(reason="timeout"):
    notify_user("robot desconectado, reconectando...")
    reconnected = await wait_for_robot_reconnect(robot_id, timeout=120)
    if reconnected:
        robot = repository.get(robot_id)   # rebind a la nueva conexión
        notify_user("robot reconectado")
        # retoma robot.connect() con la nueva conexión
    else:
        notify_user("el robot no reconectó a tiempo, cerrando sesión")
        raise   # recién acá se cierra todo el pipe
except RobotSideClosed(reason="clean_close"):
    raise   # cierre inmediato, sin esperar (sección 2)
```

Mientras el pipe está en estado "esperando", los comandos que llegan del usuario se responden
de inmediato con un error JSON-RPC ("robot no disponible"), sin tocar el canal robot (ver
"Fuera de alcance" — no se bufferizan). Timeout de espera propuesto: 2 minutos, configurable.

### 4. Api ↔ Usuario: heartbeat, siempre fatal

Mismo mecanismo de ping/pong de la sección 1, misma Api iniciando el ping. A diferencia del
lado robot, **cualquier** desconexión del usuario (cierre limpio o timeout de heartbeat) es
fatal para el pipe: se llama `discardUserConnection` y se cierra todo — no tiene sentido
esperar a que el usuario "reconecte" desde el punto de vista del pipe, ya que es él quien
inicia la sesión. El cierre limpio ya funciona hoy; el timeout de heartbeat cubre el caso
silencioso (wifi cortada, laptop suspendida) que hoy se queda colgado para siempre.

### 5. WebClient: reconexión automática

`useRobotSocket.ts` agrega:

- **Watchdog de heartbeat** (sección 1): si pasan >25s sin recibir un ping nuevo de la Api, se
  autodeclara desconectado y dispara reconexión.
- **Reconexión con backoff**: en `onclose`/`onerror` (o watchdog disparado), si no fue un
  `disconnect()` deliberado del usuario, arranca backoff 1s→30s (mismo esquema que la Pi),
  reintentando `connect()`.
- Al reconectar: rehace el handshake de auth y vuelve a solicitar la sesión con el mismo robot
  — no hay estado de sesión que "resumir" del lado servidor para el usuario, es una sesión
  nueva (a diferencia del pipe usuario↔robot ya activo, que si sobrevive, ver sección 3).
- **Dos capas de estado expuestas a la UI**, independientes entre sí:
  - Estado de transporte WS: `connected` / `reconnecting` / `error`.
  - Estado de sesión/robot, empujado por la Api (sección 3): `robot_disponible` /
    `robot_desconectado_reconectando` / `robot_no_disponible` (sesión cerrada por timeout).

## Verificación

Modo demo (`MOCK_ROBOT=1`) permite simular todo sin hardware:

- Matar/reiniciar el proceso `controller` de la Pi mientras hay un usuario conectado →
  verificar que la Api limpia el estado de inmediato (cierre limpio).
- Cortar la conexión sin que la Pi cierre prolijo (ej. bloqueando el socket con `iptables` o
  equivalente) → verificar que la Api espera el timeout de heartbeat, notifica al usuario, y
  si la Pi vuelve dentro de la ventana, el pipe se retoma sin que el usuario haga nada.
- Reiniciar la Api mientras el WebClient está conectado → verificar que el WebClient reconecta
  solo con backoff y re-establece sesión con el robot.
- Verificar que los comandos enviados durante la ventana "esperando reconexión" reciben error
  inmediato y no se ejecutan tarde en la Pi.

Estos pasos quedan como guía de verificación manual (simular un corte de red real requiere
manipular la red del entorno de desarrollo, no es un test automatizado simple de escribir).
