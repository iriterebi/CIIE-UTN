"""Modelos y manejo de comandos JSON-RPC 2.0 para el robot.

Recibe comandos desde el WS, los valida con pydantic,
los ejecuta en el controlador del robot (serial o mock)
y retorna respuestas JSON-RPC tipadas.
"""

import asyncio
import logging
from typing import Any

from pydantic import BaseModel

from .robot.responses import (
    CommandsDescriptionRobotResponse,
    DispatchErrorRobotResponse,
    DispatchOkRobotResponse,
    RobotResponse,
    StatusRobotResponse,
    StrRobotResponse,
)

logger = logging.getLogger(__name__)


# --- Modelos de entrada (comando del usuario/API) ---


class JsonRpcCommand(BaseModel):
    """Comando JSON-RPC 2.0 recibido desde la API."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[Any, Any] = {}
    id: str | int | None = None


# --- Modelos de salida (respuesta al usuario/API) ---


class JsonRpcError(BaseModel):
    code: int
    message: str


class JsonRpcResult(BaseModel):
    status: str
    method: str
    response: str | None = None
    commands_count: int | None = None


class JsonRpcResponse(BaseModel):
    """Respuesta JSON-RPC 2.0 enviada a la API."""

    jsonrpc: str = "2.0"
    result: JsonRpcResult | None = None
    error: JsonRpcError | None = None
    id: str | int | None = None


# --- Notification (mensajes sin respuesta, ej: telemetría) ---


class JsonRpcNotification(BaseModel):
    """Notification JSON-RPC 2.0 — fire-and-forget, sin id."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[Any, Any] = {}


def create_status_notification(status: dict[Any, Any]) -> JsonRpcNotification:
    """Envuelve el dict de status del robot en una notification JSON-RPC."""
    return JsonRpcNotification(method="status.update", params=status)


# --- Parsing ---


def parse_command(raw: str) -> JsonRpcCommand:
    """Parsea y valida un string JSON como comando JSON-RPC.

    Raises:
        ValidationError: si el JSON no cumple el schema.
    """
    return JsonRpcCommand.model_validate_json(raw)


# --- dispatch / to_jsonrpc ---


async def dispatch(command: JsonRpcCommand, robot) -> RobotResponse:
    """Despacha un comando y devuelve SÓLO el resultado del despacho.

    "Despacho" = el comando se validó contra el descriptor y se escribió/publicó.
    No afirma que el robot lo haya ejecutado: su salida real llega por otro camino
    (el loop de respuestas) y sale como notification sin id.

    Nunca levanta: traduce los fallos esperables a DispatchErrorRobotResponse para
    que el core no se caiga por un comando malo (hoy una excepción acá escapa del
    TaskGroup de MicroCore y tumba el agente entero).
    """
    loop = asyncio.get_running_loop()

    try:
        if command.method == "execute_sequence":
            commands = command.params.get("commands", [])
            if not isinstance(commands, list):
                raise ValueError("'commands' debe ser una lista")

            await loop.run_in_executor(None, robot.execute_sequence, commands)
            return DispatchOkRobotResponse(
                command.id, command.method, commands_count=len(commands)
            )

        raw_command = command.params.get("command", command.method)
        await loop.run_in_executor(None, robot.send_command, raw_command)
        return DispatchOkRobotResponse(command.id, command.method)

    except (ValueError, ConnectionError, OSError) as e:
        logger.error("Error despachando comando '%s': %s", command.method, e)
        return DispatchErrorRobotResponse(command.id, command.method, e)

    except Exception as e:  # noqa: BLE001 — red de seguridad deliberada
        # "Nunca levanta" es un invariante absoluto, no una lista de casos previstos.
        # Cualquier excepción que escape de acá sube por OutboxLocalStrategy.send hasta
        # el TaskGroup de MicroCore y mata el agente entero — la clase de bug que este
        # refactor existe para cerrar. logger.exception deja el stack completo en los
        # logs de la Pi, así que el bug sigue siendo diagnosticable sin tirar el proceso.
        logger.exception("Fallo inesperado despachando '%s'", command.method)
        return DispatchErrorRobotResponse(command.id, command.method, e)


# Mapeo de causa → código JSON-RPC. InvalidCommandError hereda de ValueError, así que
# el orden importa sólo para legibilidad: ambos caen en -32602.
_INVALID_PARAMS = -32602
_INTERNAL_ERROR = -32603


def _error_code(error: Exception) -> int:
    if isinstance(error, ValueError):
        return _INVALID_PARAMS
    if isinstance(error, (ConnectionError, OSError)):
        return _INTERNAL_ERROR
    return _INTERNAL_ERROR


def to_jsonrpc(resp: RobotResponse) -> JsonRpcResponse | JsonRpcNotification:
    """Traduce un RobotResponse al sobre JSON-RPC que le corresponde.

    El TIPO decide el sobre, no el valor de `request_id`: el cliente puede no mandar
    id, y un resultado de despacho sigue siendo una respuesta aunque su id sea null.
    """
    if isinstance(resp, DispatchOkRobotResponse):
        return JsonRpcResponse(
            result=JsonRpcResult(
                status="ok",
                method=resp.method,
                response=resp.detail,
                commands_count=resp.commands_count,
            ),
            id=resp.request_id,
        )

    if isinstance(resp, DispatchErrorRobotResponse):
        return JsonRpcResponse(
            error=JsonRpcError(code=_error_code(resp.error), message=str(resp.error)),
            id=resp.request_id,
        )

    if isinstance(resp, CommandsDescriptionRobotResponse):
        return JsonRpcNotification(
            method="command.update", params={"commands": resp.toList()}
        )

    if isinstance(resp, StatusRobotResponse):
        return JsonRpcNotification(method="status.update", params=resp.status)

    if isinstance(resp, StrRobotResponse):
        return JsonRpcNotification(method="robot.output", params={"data": resp.text})

    logger.warning("RobotResponse sin traducción específica: %s", type(resp).__name__)
    return JsonRpcNotification(method="robot.output", params={"data": str(resp)})
