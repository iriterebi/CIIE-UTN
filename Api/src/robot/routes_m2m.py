"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

from typing import Annotated
from uuid import UUID as PythonUUID

from aioreactive import AsyncSubject
from fastapi import APIRouter, Depends, WebSocket
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .handshake import HandshakeService
from .robot import (
    RobotService, RobotServiceDep, Robot, RobotConnection, get_current_robot,
    RobotRegistrationInput, RobotRegistrationOutput,
)
from .robot.ipc_user_robot_comunication import create_subject
from ..auth.services.encryption import AccessToken

router = APIRouter(tags=["robots", "m2m"])

security = HTTPBasic()


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


@router.post("/handshake", response_model=AccessToken)
def login(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    handshake_service: Annotated[HandshakeService, Depends(HandshakeService)]
) -> AccessToken:
    return handshake_service.create_access_token_by_basic_credentials(credentials)


@router.websocket("/commands/{auth_token}")
async def websocket_endpoint(
    websocket: WebSocket,
    ipc: Annotated[AsyncSubject, Depends(create_subject)],
    robot_service: Annotated[RobotService, Depends(RobotService)],
    auth_token: str
):
    robot: Robot = get_current_robot(robot_service, auth_token)

    print("New connection")

    await RobotConnection(ipc, robot_service, robot).connect(websocket)
