"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

import logging
from typing import Annotated
from uuid import UUID as PythonUUID

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..services.handshake_service import HandshakeService
from ..services import (
    RobotServiceDep, RobotRegistrationInput, RobotRegistrationOutput, RobotHandshakeResult
)
from ..utils.crockford_base32 import uuid_to_crockford_base32
from ...auth.entities import AccessToken

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
        topic=f"/robot/r{uuid_to_crockford_base32(robot.id)}"
    )
