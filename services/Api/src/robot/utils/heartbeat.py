"""Heartbeat de aplicación: ping periódico + timeout de pong.

Mecanismo agnóstico al transporte, reutilizado tanto para la conexión
Api↔Pi (`routes/m2m.py`) como Api↔Usuario
(`services/ipc_user_robot_comunication.py`) para detectar caídas
silenciosas que no generan un cierre de socket limpio (ver
docs/superpowers/specs/2026-07-06-resiliencia-reconexion-design.md).
"""

import asyncio
from typing import Awaitable, Callable, Never

PING_INTERVAL_SECONDS: float = 10.0
PONG_TIMEOUT_SECONDS: float = 15.0


class HeartbeatTimeoutError(Exception):
    """No se recibió el pong correspondiente dentro del timeout configurado."""


async def run_heartbeat_watchdog(
    send_ping: Callable[[], Awaitable[None]],
    pong_received: asyncio.Event,
    *,
    ping_interval: float = PING_INTERVAL_SECONDS,
    pong_timeout: float = PONG_TIMEOUT_SECONDS,
) -> Never:
    """Envía un ping cada `ping_interval` segundos y espera su pong.

    Levanta `HeartbeatTimeoutError` si no se recibe el pong dentro de
    `pong_timeout` segundos. El caller es responsable de: (1) hacer
    `pong_received.set()` cuando llega un mensaje `{"type": "pong"}`
    del peer, y (2) correr esta corutina concurrente con el loop de
    recepción física (ej. en un `asyncio.TaskGroup`), para que el
    timeout pueda efectivamente cortar la conexión.
    """
    while True:
        pong_received.clear()
        await send_ping()
        try:
            await asyncio.wait_for(pong_received.wait(), timeout=pong_timeout)
        except asyncio.TimeoutError as e:
            raise HeartbeatTimeoutError() from e
        await asyncio.sleep(ping_interval)
