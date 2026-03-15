from typing import List, Annotated
from uuid import UUID as PythonUUID

from fastapi import Depends, HTTPException
from jwt import InvalidTokenError

from ..entities.errors import RobotNotFoundException, InvalidRobotStatusException
from ...auth.services import EncryptionServiceDep
from ...auth.entities import TokenStrDep
from ..repositories.robot import RobotRepositoryDep

from ..entities import Robot, RobotInput, RobotStatus, RobotRegistrationInput, RobotApprovalInput


class RobotService:
    def __init__(
            self,
            repository: RobotRepositoryDep,
            encryption_service: EncryptionServiceDep,
    ):
        self.repository = repository
        self.encryption_service = encryption_service

    def list_robots(self) -> List[Robot]:
        return self.repository.list()

    def get_robot_by_id(self, robot_id: str | PythonUUID) -> Robot | None:
        return self.repository.get_by_id(robot_id)

    def exists(self, robot_id: str | PythonUUID) -> bool:
        return self.get_robot_by_id(robot_id) is not None

    def validate_exists_robot(self, robot_id: str | PythonUUID) -> None:
        try:
            if not self.exists(robot_id):
                raise RobotNotFoundException(robot_id)
        except ValueError as e:
            raise RobotNotFoundException(robot_id) from e

    def get_robot_by_external_identifier(self, external_identifier: str) -> Robot | None:
        return self.repository.get_by_external_identifier(external_identifier)

    def create_robot(self, robotInput: RobotInput) -> Robot:
        hashed_psw = self.encryption_service.encrypt_psw(robotInput.psw)

        robot_data = robotInput.model_dump(exclude={"psw"}, mode="json")
        robot_data["psw"] = hashed_psw

        robot = Robot.model_validate(robot_data)
        return self.repository.save(robot)

    def register_robot(self, registration: RobotRegistrationInput) -> Robot:
        existing = self.get_robot_by_external_identifier(
            str(registration.external_identifier))

        if existing:
            return existing

        hashed_psw = self.encryption_service.encrypt_psw(registration.psw)
        robot = Robot.model_validate({
            "external_identifier": str(registration.external_identifier),
            "psw": hashed_psw,
            "status": RobotStatus.PENDING_APPROVAL,
            "name": None,
        })
        return self.repository.save(robot)

    def approve_robot(self, robot_id: PythonUUID, approval: RobotApprovalInput) -> Robot:
        robot = self.get_robot_by_id(robot_id)

        if not robot:
            raise RobotNotFoundException(robot_id)
        if robot.status != RobotStatus.PENDING_APPROVAL:
            raise InvalidRobotStatusException(
                robot_id, robot.status, RobotStatus.PENDING_APPROVAL)

        robot.name = approval.name
        robot.description = approval.description
        robot.status = RobotStatus.APPROVED

        return self.repository.save(robot)

    def reject_robot(self, robot_id: PythonUUID) -> Robot:
        robot = self.get_robot_by_id(robot_id)
        if not robot:
            raise RobotNotFoundException(robot_id)
        if robot.status != RobotStatus.PENDING_APPROVAL:
            raise InvalidRobotStatusException(
                robot_id, robot.status, RobotStatus.PENDING_APPROVAL)

        robot.status = RobotStatus.REJECTED

        return self.repository.save(robot)

    def list_robots_by_status(self, status: RobotStatus) -> List[Robot]:
        return self.repository.list_by_status(status)

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
    try:
        robot = robot_service.get_robot_by_token(token)

        if not robot:
            raise HTTPException(status_code=401, detail="Robot not found")

        return robot
    except InvalidTokenError as e:
        raise HTTPException(status_code=401, detail="Invaid token") from e
