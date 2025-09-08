from typing import List, Annotated
from uuid import UUID as PythonUUID
from fastapi import Depends, HTTPException

from src.db_connection import DbSessionDep
from src.auth.services.encryption import EncryptionServiceDep, TokenStrDep

from .robot import Robot, RobotInput


class RobotService:
    def __init__(
        self,
        db_session: DbSessionDep,
        encryption_service: EncryptionServiceDep,
    ):
        self.db_session = db_session
        self.encryption_service = encryption_service

    def list_robots(self) -> List[Robot]:
        return self.db_session.query(Robot).all()

    def get_robot_by_id(self, robot_id: str) -> Robot | None:
        # type: ignore
        return self.db_session.query(Robot).filter(Robot.id == PythonUUID(robot_id)).first()

    def get_robot_by_external_identifier(self, external_identifier: str) -> Robot | None:
        return self.db_session.query(Robot).filter(Robot.external_identifier == external_identifier).first()

    def create_robot(self, robotInput: RobotInput) -> Robot:
        hashed_psw = self.encryption_service.encrypt_psw(robotInput.psw)

        # Create a dictionary from the input, excluding the plain password
        robot_data = robotInput.model_dump(exclude={"psw"})

        # Add the hashed password and ensure external_identifier is a string
        robot_data["psw"] = hashed_psw
        robot_data["external_identifier"] = str(robotInput.external_identifier)

        # Create the Robot instance from the validated and prepared data
        robot = Robot.model_validate(robot_data)

        self.db_session.add(robot)
        self.db_session.commit()
        self.db_session.refresh(robot)
        return robot

    def get_robot_by_token(self, token: str) -> Robot | None:
        data: dict = self.encryption_service.decode_token(token)

        role = data.get("role", None)
        if role != "robot":
            return None

        sub = data.get("sub", None)
        if not sub: return None

        return self.get_robot_by_id(sub)


RobotServiceDep = Annotated[RobotService, Depends(RobotService)]


def get_current_robot(
    robot_service: RobotServiceDep,
    token: TokenStrDep
) -> Robot:
    robot = robot_service.get_robot_by_token(token)

    if not robot:
        raise HTTPException(status_code=401, detail="Robot not found")

    return robot
