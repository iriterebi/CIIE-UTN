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

from ..entities.robot import Robot, RobotStreamAutentication
from ..adapters import ProxyStreamSource
from ..repositories.robot_connection import RobotConnectionRepositoryDep
from ..services.handshake_service import HandshakeService, HandshakeServiceDep
from ..services import (
    RobotServiceDep, RobotRegistrationInput, RobotRegistrationOutput, RobotHandshakeResult
)
from ..utils.crockford_base32 import uuid_to_crockford_base32

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
    accessToken, robot = handshake_service.create_access_token_by_basic_credentials(credentials)
    return RobotHandshakeResult(
        access_token=accessToken,
        topic=f"/robot/r{uuid_to_crockford_base32(str(robot.id))}"
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

    accepting: bool = False

    async def idk(val: bool):
        nonlocal accepting
        accepting = val
        logger.info("Accepting: %s", accepting)

    def idk2(val: bool):
        return lambda: idk(val)

    streamSource = ProxyStreamSource(
        on_recieve=lambda data: websocket.send_json(data),  # pyright: ignore[reportAny]
        on_accept=idk2(True),
        on_disconnect=idk2(False),
        on_idle_changed=idk
    )


    _ = robot_connection_repository.addRobotConnection(robot, streamSource)


    async for message in websocket.iter_json():
        logger.info("Message received: %s", message)
        if accepting:
            await streamSource.enqueue_data(message)  # pyright: ignore[reportUnreachable]



