"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

from typing import Annotated
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .handshake import HandshakeService
from .robot import (
    RobotServiceDep, RobotRegistrationInput, RobotRegistrationOutput,
)
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
