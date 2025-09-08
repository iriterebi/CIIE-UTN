from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasicCredentials
from src.auth.services.encryption import EncryptionServiceDep, AccessToken
from ..robot import Robot, RobotService


class HandshakeService:
    def __init__(
        self,
        encryption_service: EncryptionServiceDep,
        robot_service: Annotated[RobotService, Depends(RobotService)]
    ):
        self.encryption_service = encryption_service
        self.robot_service = robot_service

    def create_access_token_by_basic_credentials(self, credentials: HTTPBasicCredentials) -> AccessToken:
        robot = self.robot_service.get_robot_by_external_identifier(credentials.username)

        if not robot:
            raise HTTPException(
                status_code=400, detail="Incorrect username")

        if not self.encryption_service.verify_pwd(credentials.password, robot.psw):
            raise HTTPException(
                status_code=400, detail="Incorrect password")

        return self.create_access_token(robot)

    def create_access_token(self, robot: Robot) -> AccessToken:
        token = self.encryption_service.create_bearer_access_token(data={
            "sub": str(robot.id),
            "role": "robot",
            "scope": "broker:report_log broker:listen_commands"
        })
        return token


HandshakeServiceDep = Annotated[HandshakeService, Depends(HandshakeService)]
