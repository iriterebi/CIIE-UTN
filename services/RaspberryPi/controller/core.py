"""Micro core: enrutador puro entre strategies.

No transforma datos — solo mueve mensajes en formato interno
entre el strategy local y el strategy remoto.
"""

import asyncio
import logging

from .strategy.base import Strategy

logger = logging.getLogger(__name__)


class MicroCore:

    def __init__(self, *, local: Strategy, remote: Strategy):
        self.local: Strategy = local
        self.remote: Strategy = remote

    async def run(self) -> None:
        """Arranca ambos strategies y enruta mensajes entre ellos."""
        await self.remote.start()
        await self.local.start()
        logger.info("Micro core iniciado — enrutando mensajes")

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._route_remote_to_local())  # pyright: ignore[reportUnusedCallResult]
                tg.create_task(self._route_local_to_remote())  # pyright: ignore[reportUnusedCallResult]
        finally:
            await self.stop()

    async def stop(self):
            await self.local.stop()
            await self.remote.stop()
            logger.info("Micro core detenido")

    async def _route_remote_to_local(self) -> None:
        """Remoto → Local: comandos de la API/rosbridge al robot."""
        while True:
            message = await self.remote.receive()
            await self.local.send(message)

    async def _route_local_to_remote(self) -> None:
        """Local → Remoto: respuestas/status del robot a la API/rosbridge."""
        while True:
            message = await self.local.receive()
            await self.remote.send(message)
