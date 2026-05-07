from uuid import UUID as PythonUUID

from fastapi import APIRouter
from typing import Annotated
from fastapi import Depends

from ..services import (
    RobotService, RobotServiceDep, Robot, RobotInput, RobotOutput,
    RobotStatus, RobotApprovalInput,
)

router = APIRouter(tags=["robots", "admin"])


@router.get("/list", response_model=list[RobotOutput])
def list_robots(
    robot_service: Annotated[RobotService, Depends(RobotService)]
) -> list[RobotOutput]:
    return robot_service.list_robots()


@router.get("/pending", response_model=list[RobotOutput])
def list_pending_robots(
    robot_service: RobotServiceDep,
) -> list[RobotOutput]:
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

