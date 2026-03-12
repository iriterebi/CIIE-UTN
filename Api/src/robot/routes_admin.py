from uuid import UUID as PythonUUID

from aioreactive import AsyncSubject
from fastapi import APIRouter
from typing import Annotated, List
from fastapi import Depends
from reactivex.subject import Subject
from .robot.ipc_user_robot_comunication import create_subject


# from ..auth.services.user import User, get_current_user
from .robot import (
    RobotService, RobotServiceDep, Robot, RobotInput, RobotOutput, RobotCommand,
    RobotStatus, RobotApprovalInput,
)

router = APIRouter(tags=["robots", "admin"])


@router.get("/list", response_model=List[RobotOutput])
def list_robots(
    # current_user: Annotated[User, Depends(get_current_user)],
    robot_service: Annotated[RobotService, Depends(RobotService)]
) -> List[RobotOutput]:
    return robot_service.list_robots()


@router.get("/pending", response_model=List[RobotOutput])
def list_pending_robots(
    robot_service: RobotServiceDep,
) -> List[RobotOutput]:
    return robot_service.list_robots_by_status(RobotStatus.PENDING_APPROVAL)


@router.get("/{robot_id}", response_model=RobotOutput)
def get_robot(robot_service: Annotated[RobotService, Depends(RobotService)], robot_id: str) -> Robot:
    return robot_service.get_robot_by_id(robot_id)


@router.post("/create", response_model=RobotOutput)
def create_robot(
    robot_service: Annotated[RobotService, Depends(RobotService)],
    robot: RobotInput
) -> Robot:
    return robot_service.create_robot(robot)


@router.post("/{robot_id}/approve", response_model=RobotOutput)
def approve_robot(
    robot_service: RobotServiceDep,
    robot_id: str,
    approval: RobotApprovalInput,
) -> Robot:
    return robot_service.approve_robot(PythonUUID(robot_id), approval)


@router.post("/{robot_id}/reject", response_model=RobotOutput)
def reject_robot(
    robot_service: RobotServiceDep,
    robot_id: str,
) -> Robot:
    return robot_service.reject_robot(PythonUUID(robot_id))


@router.post("/send_command")
async def send_command(
    ipc: Annotated[AsyncSubject, Depends(create_subject)],
    command: RobotCommand
):
    await ipc.asend(command)
    return {"message": "Command sent"}
