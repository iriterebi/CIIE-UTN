"""Servidor Unix socket para gestión del micro core.

Escucha conexiones en un Unix socket y despacha requests JSON-RPC 2.0.
Protocolo: mensajes JSON delimitados por newline.
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Self

logger = logging.getLogger(__name__)


class SocketServer:
    """Server asyncio sobre Unix socket con dispatch JSON-RPC 2.0."""

    def __init__(self, socket_path: str):
        self._socket_path = socket_path
        self._server: asyncio.Server | None = None
        self._methods: dict[str, Callable[..., Any]] = {}

        self.register_method("help", self._help_handler)  # pyright: ignore[reportUnusedCallResult]

    def _help_handler(self) -> dict[str, str]:
        """Lista los comandos disponibles y su descripción."""
        _help: dict[str, str] = {}

        for handler in self._methods.items():
            _help[handler[0]] = handler[1].__doc__ or ""


        return _help


    def register_method(self, name: str, handler: Callable[..., Any]) -> Self:
        """Registra un método JSON-RPC que el server puede despachar."""
        self._methods[name] = handler

        return self

    async def start(self) -> None:
        # Limpiar socket previo si existe
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._server = await asyncio.start_unix_server(
            self._handle_connection, path=self._socket_path
        )
        logger.info("Socket server escuchando en %s", self._socket_path)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        logger.info("Socket server detenido")

    async def serve_forever(self) -> None:
        """Bloquea sirviendo conexiones. Para usar dentro de un TaskGroup."""
        if not self._server:
            await self.start()
        assert self._server is not None
        await self._server.serve_forever()

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Maneja una conexión individual del CLI."""
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                response = await self._dispatch(line.decode().strip())
                writer.write((json.dumps(response) + "\n").encode())
                await writer.drain()
        except ConnectionResetError:
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def _dispatch(self, raw: str) -> dict[str, Any]:
        """Parsea un request JSON-RPC y despacha al handler."""
        try:
            request = json.loads(raw)
        except json.JSONDecodeError:
            return self._error(None, -32700, "Parse error")

        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method or not isinstance(method, str):
            return self._error(request_id, -32600, "Invalid request")

        handler = self._methods.get(method)
        if not handler:
            return self._error(request_id, -32601, f"Method not found: {method}")

        try:
            result = handler(**params) if params else handler()
            if asyncio.iscoroutine(result):
                result = await result
            return {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id,
            }
        except Exception as e:
            logger.error("Error ejecutando método '%s': %s", method, e)
            return self._error(request_id, -32603, str(e))

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "error": {"code": code, "message": message},
            "id": request_id,
        }
