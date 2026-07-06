"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

import asyncio
import logging
from typing import Annotated, Any
from uuid import UUID as PythonUUID
from fastapi import APIRouter, Depends, WebSocket
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from jwt import ExpiredSignatureError
from pydantic import ValidationError

from ..entities.robot import Robot, RobotStreamAutentication
from ..adapters import ProxyStreamSource
from ..repositories.robot_connection import RobotConnectionRepositoryDep
from ..services.handshake_service import HandshakeService, HandshakeServiceDep
from ..services import (
    RobotServiceDep, RobotRegistrationInput, RobotRegistrationOutput, RobotHandshakeResult, RobotResponse
)
from ..utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog

router = APIRouter(tags=["robots", "m2m"])

security = HTTPBasic()

logger = logging.getLogger(__name__)

@router.post("/register", response_model=RobotRegistrationOutput)
def register_robot(
    robot_service: RobotServiceDep,
    registration: RobotRegistrationInput,
) -> RobotRegistrationOutput:
    robot = robot_service.register_robot(registration)
    return RobotRegistrationOutput(
        external_identifier=PythonUUID(robot.external_identifier),
        status=robot.status,
    )


@router.post("/handshake", response_model=RobotHandshakeResult)
def login(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    handshake_service: Annotated[HandshakeService, Depends(HandshakeService)]
) -> RobotHandshakeResult:
    accessToken, _ = handshake_service.create_access_token_by_basic_credentials(credentials)
    return RobotHandshakeResult(
        access_token=accessToken,
    )

@router.websocket('/connect')
async def robot_connection(
    websocket: WebSocket,
    robot_connection_repository: RobotConnectionRepositoryDep,
    robot_handshake_service: HandshakeServiceDep
):
    await websocket.accept()

    # == validate

    await websocket.send_json({
        "jsonrpc": "2.0",
        "method": "send_credentials",
        "params": [],
        "id": 1
    })

    robot: Robot | None

    try:
        access_bare_data: dict[str, Any] = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny, reportExplicitAny]
        access_data = RobotStreamAutentication.model_validate(access_bare_data)
        robot= robot_handshake_service.get_robot_by_token(access_data.token)
    except ExpiredSignatureError as e:
        logger.error(e)
        await websocket.send_json({
            "status": "error",
            "message": "Token expired"
        })
        await websocket.close()
        return
    except Exception as e:
        logger.error(e)
        await websocket.send_json({
            "status": "error",
            "message": "Error validating token"
        })
        await websocket.close()
        return


    if robot is None:
        await websocket.send_json({
            "status": "error",
            "message": "Robot not found"
        })
        await websocket.close()
        return
    else:
        await websocket.send_json({
            "status": "success auth",
        })

    # ====

    # Flag activado cuando hay un usuario consumiendo el pipe (gated por
    # on_idle_changed desde RobotConnection). Sin consumidor → no se
    # enqueuan mensajes para evitar llenar la queue sin lectores.
    pipe_active: bool = False

    async def set_pipe_active(idle: bool) -> None:
        nonlocal pipe_active
        pipe_active = not idle
        logger.info("Pipe active: %s", pipe_active)

    async def noop_async() -> None:
        return None

    send_lock = asyncio.Lock()

    async def _send_json_locked(data: Any) -> None:  # pyright: ignore[reportExplicitAny, reportAny]
        async with send_lock:
            await websocket.send_json(data)

    streamSource = ProxyStreamSource(
        on_recieve=_send_json_locked,
        on_accept=noop_async,
        on_disconnect=noop_async,
        on_idle_changed=set_pipe_active,
    )

    _ = robot_connection_repository.addRobotConnection(robot, streamSource)

    pong_received = asyncio.Event()
    pong_received.set()

    async def _send_ping() -> None:
        await _send_json_locked({"type": "ping"})

    async def _receive_loop() -> None:
        # No usamos `websocket.iter_json()`: internamente atrapa
        # `WebSocketDisconnect` y termina el generador en silencio, sin
        # propagar nada. Eso hace que, ante cualquier cierre del socket
        # (voluntario o no), este loop termine "exitosamente" y la única
        # señal de corte termine siendo, siempre, el timeout del
        # heartbeat — nunca `except* Exception` (clean_close). Llamando a
        # `receive_json()` directo, `WebSocketDisconnect` se propaga y
        # permite distinguir el cierre limpio del timeout, tal como
        # corresponde.
        while True:
            message: Any = await websocket.receive_json()  # pyright: ignore[reportAny]
            logger.info("Message received: %s", message)
            if isinstance(message, dict) and message.get("type") == "pong":
                pong_received.set()
                continue
            if not pipe_active:
                continue
            try:
                validated = RobotResponse.model_validate(message)
            except ValidationError:
                logger.warning("Mensaje del robot mal formado, descartando: %s", message)
                continue
            await streamSource.enqueue_data(validated.model_dump(mode="python"))

    disconnect_reason = "clean_close"
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_receive_loop())
            tg.create_task(run_heartbeat_watchdog(_send_ping, pong_received))
    except* HeartbeatTimeoutError:
        disconnect_reason = "timeout"
        logger.warning("Sin heartbeat del robot %s, cerrando conexión", robot.id)
    except* Exception:
        disconnect_reason = "clean_close"
        logger.info("Conexión del robot %s cerrada limpiamente", robot.id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

        # Invariante: para que un `clean_close` derribe el pipe de una vez
        # (sin pasar nunca por la rama de espera de reconexión),
        # `mark_disconnected` y `discardRobotConnection(discardPipeddConnections=True)`
        # deben correr de forma síncrona respecto a la tarea supervisora del
        # pipe (sin ningún `await` que ceda el control real). Si alguna vez
        # se le agrega I/O async genuino a `mark_disconnected`, esta
        # distinción entre `clean_close` y `timeout` puede romperse.
        await streamSource.mark_disconnected(disconnect_reason)

        if disconnect_reason == "timeout":
            robot_connection_repository.discardDeadRobotConnection(robot)
        else:
            robot_connection_repository.discardRobotConnection(robot, discardPipeddConnections=True)
