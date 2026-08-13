#!/usr/bin/env -S python3 -m

"""CLI para gestión del controlador de robot.

Proceso separado que se conecta al micro core vía Unix socket.
Protocolo: JSON-RPC 2.0 delimitado por newlines.

Uso:
    directamente desde CLI:
        cli
        cli help
        cli status

    o como módulo de python:
        python -m cli help
        python -m cli status
"""

import asyncio
import json
import sys
from textwrap import dedent
from typing import Any
import uuid
from controller.type_defs import CoreStatusData, StatusData, JsonRpcRequest, JsonRpcResponse

DEFAULT_SOCKET_PATH = "/tmp/robot-controller.sock"

async def send_request[T](socket_path: str, method: str, params: dict[Any, Any] | None = None) -> JsonRpcResponse[T]:
    """Conecta al socket, envía un request JSON-RPC y retorna la respuesta."""
    reader, writer = await asyncio.open_unix_connection(socket_path)

    request_id = uuid.uuid4()

    payload: JsonRpcRequest = {
        "jsonrpc": "2.0",
        "method": method,
        "id": str(request_id),
    }
    if params:
        payload["params"] = params

    request = json.dumps(payload)
    writer.write((request + "\n").encode())
    await writer.drain()

    line = await reader.readline()
    writer.close()
    await writer.wait_closed()

    # TODO: revisar el id del response

    return json.loads(line.decode())  # pyright: ignore[reportAny]


def print_status(response: JsonRpcResponse[CoreStatusData]) -> None:
    """Imprime el resultado de status de forma legible."""
    if "error" in response:
        err = response["error"]
        print(f"Error [{err['code']}]: {err['message']}")
        return

    result = response.get("result", {})
    print(f"Core: {result.get('core', '?')}")

    print_strategy_status("local", result.get("local", {}))
    print_strategy_status("remote", result.get("remote", {}))

def print_strategy_status(scope: str, status: StatusData) -> None:
    print(f"Strategy {scope}:  {status.get('name', '?')} [{status.get('status', '?')}]")

def print_help() -> None:
    print(dedent(f"""\
        Uso: {sys.argv[0]} [comando] [argumentos...]

          CLI de gestión del controlador de robot.
          Se comunica con el micro core vía Unix socket.

        Comandos:
          help                            \t Muestra esta ayuda
          switch-telemetry {{on|off}}     \t Habilita/deshabilita telemetría local
          status [local|remote]           \t Estado del core y los strategies
          start {{local|remote}}          \t Arranca un strategy
          stop {{local|remote}}           \t Detiene un strategy
          pause {{local|remote}}          \t Pausa un strategy
          resume {{local|remote}}         \t Reanuda un strategy
          use {{local|remote}} <strategy>
    """))


def print_response(response: JsonRpcResponse) -> None:
    """Imprime una respuesta JSON-RPC genérica."""
    if "error" in response:
        err = response["error"]
        print(f"Error [{err['code']}]: {err['message']}")
    else:
        result = response.get("result", {})
        if isinstance(result, dict):
            for key, value in result.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {result}")


def check_response(response: JsonRpcResponse) -> bool:
    """Imprime una respuesta JSON-RPC de error."""

    if "error" in response:
        err = response["error"]
        print(f"Error [{err['code']}]: {err['message']}")
        return False

    return True


async def cmd_status(socket_path: str, scope: str | None = None) -> None:
    if scope is None:
        print_status(await send_request(socket_path, "status"))
    else:
        response: JsonRpcResponse[StatusData] = await send_request(socket_path, f"connection::{scope}::status")
        if check_response(response):
            print_strategy_status(scope, response["result"])
        else:
            sys.exit(1)



async def cmd_switch_telemetry(socket_path: str, command: str) -> None:
    if command not in ("on", "off"):
        print("Uso: switch-telemetry {on|off}")
        sys.exit(1)
    response: JsonRpcResponse[StatusData] = await send_request(socket_path, "switch", {"enabled": command == "on"})
    if check_response(response):
        print_strategy_status("local", response["result"])
    else:
        sys.exit(1)


async def cmd_connection_action(socket_path: str, action: str, scope: str) -> None:
    if scope not in ("local", "remote"):
        print(f"Uso: {action} {{local|remote}}")
        sys.exit(1)
    print_response(await send_request(socket_path, f"connection::{scope}::{action}"))


async def main(args: list[str]) -> None:
    socket_path = DEFAULT_SOCKET_PATH
    try:
        match args:
            case ["help"]:
                print_help()
            case ["status"]:
                await cmd_status(socket_path)
            case ["status", scope]:
                await cmd_status(socket_path, scope)
            case ["switch-telemetry", command]:
                await cmd_switch_telemetry(socket_path, command)
            case ["start", scope]:
                await cmd_connection_action(socket_path, "start", scope)
            case ["stop", scope]:
                await cmd_connection_action(socket_path, "stop", scope)
            case ["pause", scope]:
                await cmd_connection_action(socket_path, "pause", scope)
            case ["resume", scope]:
                await cmd_connection_action(socket_path, "resume", scope)
            # case ["use", scope, strategy]:
            #     await cmd_use(socket_path, scope, strategy)
            case _:
                print("Comando desconocido. Use 'help'.")
                sys.exit(1)

    except (ConnectionRefusedError, FileNotFoundError):
        print("Error: no se pudo conectar al controlador.")
        print(f"  ¿Está corriendo? Socket: {socket_path}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
