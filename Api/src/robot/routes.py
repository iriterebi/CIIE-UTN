"""
FastAPI router for robot-related endpoints.

This module defines the API routes for interacting with robots
"""

from typing import Annotated, List
from fastapi import APIRouter, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..auth.services.user import User, get_current_user
from ..auth.services.encryption import AccessToken
from .robot import RobotService, Robot
from .handshake import HandshakeService

router = APIRouter(tags=["robots"])

security = HTTPBasic()

@router.get("/list", response_model=List[Robot])
def list_robots(
    current_user: Annotated[User, Depends(get_current_user)],
    robot_service: Annotated[RobotService, Depends(RobotService)]
) -> List[Robot]:
    return robot_service.list_robots(current_user)

@router.post("/handshake", response_model=AccessToken)
def login(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
    handshake_service: Annotated[HandshakeService, Depends(HandshakeService)]
) -> AccessToken:
    return handshake_service.create_access_token_by_basic_credentials(credentials)
