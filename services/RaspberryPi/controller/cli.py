#!/usr/bin/env python3

"""CLI para gestión del controlador de robot.

Proceso separado que se conecta al micro core vía Unix socket.
Protocolo: JSON-RPC 2.0 delimitado por newlines.

Uso:
    directamente desde CLI:
        controller.cli
        controller.cli help
        controller.cli status

    o como módulo de python:
        python -m controller.cli help
        python -m controller.cli status
        python -m controller.cli              # default: help
"""

import asyncio
import json
import sys
from textwrap import dedent

DEFAULT_SOCKET_PATH = "/tmp/robot-controller.sock"


async def send_request(socket_path: str, method: str, params: dict | None = None) -> dict:
    """Conecta al socket, envía un request JSON-RPC y retorna la respuesta."""
    reader, writer = await asyncio.open_unix_connection(socket_path)

    payload: dict = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1,
    }
    if params:
        payload["params"] = params

    request = json.dumps(payload)
    writer.write((request + "\n").encode())
    await writer.drain()

    line = await reader.readline()
    writer.close()
    await writer.wait_closed()

    return json.loads(line.decode())


def print_status(response: dict) -> None:
    """Imprime el resultado de status de forma legible."""
    if "error" in response:
        err = response["error"]
        print(f"Error [{err['code']}]: {err['message']}")
        return

    result = response.get("result", {})
    print(f"Core: {result.get('core', '?')}")

    local = result.get("local", {})
    print(f"Strategy local:  {local.get('name', '?')} [{local.get('status', '?')}]")

    remote = result.get("remote", {})
    print(f"Strategy remoto: {remote.get('name', '?')} [{remote.get('status', '?')}]")

def print_usage_help() -> None:
    print(dedent(f"""\
        Uso: {sys.argv[0]} [comando]

          CLI de gestión del controlador de robot.
          Se comunica con el micro core vía Unix socket.
    """))


def print_controller_help(response: dict) -> None:
    """Imprime los comandos disponibles desde la respuesta del server."""
    if "error" in response:
        err = response["error"]
        print(f"Error [{err['code']}]: {err['message']}")
        return

    result = response.get("result", {})
    if not result:
        print("  No hay comandos registrados.")
        return

    print("Comandos disponibles:")
    for method, description in result.items():
        print(f"  {method:15s} {description}")


def print_response(response: dict) -> None:
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


BUILTIN_COMMANDS = {"help", "status", "switch"}


async def main(args: list[str]) -> None:
    socket_path = DEFAULT_SOCKET_PATH
    command = args[0] if args else "help"
    try:
        match command:
            case "help":
                print_usage_help()
                response = await send_request(socket_path, "help")
                print_controller_help(response)

            case "status":
                response = await send_request(socket_path, "status")
                print_status(response)

            case "switch":
                arg = args[1] if len(args) > 1 else None
                if arg not in ("on", "off"):
                    print("Uso: switch <on|off>")
                    sys.exit(1)
                enabled = arg == "on"
                response = await send_request(socket_path, "switch", {"enabled": enabled})
                if "error" in response:
                    err = response["error"]
                    print(f"Error [{err['code']}]: {err['message']}")
                else:
                    state = "habilitada" if response.get("result", {}).get("telemetry") else "deshabilitada"
                    print(f"Telemetría {state}")

            case _:
                # Scoped command: joinear args con ::
                method = "::".join(args)
                response = await send_request(socket_path, method)
                print_response(response)

    except (ConnectionRefusedError, FileNotFoundError):
                print("Error: no se pudo conectar al controlador.")
                print(f"  ¿Está corriendo? Socket: {socket_path}")
                sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
