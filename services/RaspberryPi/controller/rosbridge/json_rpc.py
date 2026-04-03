"""Modelos y manejo de comandos JSON-RPC 2.0 para el robot.

Recibe comandos del topic ROS, los valida con pydantic,
los ejecuta en el controlador del robot (serial o mock)
y retorna respuestas JSON-RPC tipadas.
"""

import asyncio
import logging

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --- Modelos de entrada (comando del usuario/API) ---

class JsonRpcCommand(BaseModel):
    """Comando JSON-RPC 2.0 recibido via rosbridge."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}
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
    """Respuesta JSON-RPC 2.0 enviada via rosbridge."""
    jsonrpc: str = "2.0"
    result: JsonRpcResult | None = None
    error: JsonRpcError | None = None
    id: str | int | None = None


# --- Notification (mensajes sin respuesta, ej: telemetría) ---

class JsonRpcNotification(BaseModel):
    """Notification JSON-RPC 2.0 — fire-and-forget, sin id."""
    jsonrpc: str = "2.0"
    method: str
    params: dict = {}


def create_status_notification(status: dict) -> JsonRpcNotification:
    """Envuelve el dict de status del robot en una notification JSON-RPC."""
    return JsonRpcNotification(method="status.update", params=status)


# --- Parsing ---

def parse_command(raw: str) -> JsonRpcCommand:
    """Parsea y valida un string JSON como comando JSON-RPC.

    Raises:
        ValidationError: si el JSON no cumple el schema.
    """
    return JsonRpcCommand.model_validate_json(raw)


# --- Handler ---

async def handle_json_rpc(command: JsonRpcCommand, robot) -> JsonRpcResponse:
    """Procesa un comando JSON-RPC 2.0 validado y retorna la respuesta.

    Ejecuta la I/O serial en run_in_executor para no bloquear el event loop.
    """
    loop = asyncio.get_running_loop()

    try:
        if command.method == "execute_sequence":
            commands = command.params.get("commands", [])
            if not isinstance(commands, list):
                return _error_response(
                    command.id, -32602, "'commands' debe ser una lista"
                )
            await loop.run_in_executor(None, robot.execute_sequence, commands)
            result = JsonRpcResult(
                status="ok", method=command.method, commands_count=len(commands)
            )

        else:
            raw_command = command.params.get("command", command.method)
            await loop.run_in_executor(None, robot.send_command, raw_command)
            response = await loop.run_in_executor(None, robot.read_response)
            result = JsonRpcResult(
                status="ok", method=command.method, response=response
            )

    except (ConnectionError, EnvironmentError) as e:
        logger.error("Error ejecutando comando '%s': %s", command.method, e)
        return _error_response(command.id, -32603, str(e))

    return JsonRpcResponse(result=result, id=command.id)


def _error_response(
    request_id: str | int | None, code: int, message: str
) -> JsonRpcResponse:
    return JsonRpcResponse(error=JsonRpcError(code=code, message=message), id=request_id)
