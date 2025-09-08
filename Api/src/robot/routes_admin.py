from fastapi import APIRouter
from typing import Annotated, List
from fastapi import Depends
from reactivex.subject import Subject
from .robot.ipc_user_robot_comunication import create_subject


# from ..auth.services.user import User, get_current_user
from .robot import RobotService, Robot, RobotInput, RobotOutput, RobotCommand

router = APIRouter(tags=["robots", "admin"])


@router.get("/list", response_model=List[RobotOutput])
def list_robots(
    # current_user: Annotated[User, Depends(get_current_user)],
    robot_service: Annotated[RobotService, Depends(RobotService)]
) -> List[RobotOutput]:
    return robot_service.list_robots()


@router.get("/{robot_id}", response_model=RobotOutput)
def get_robot(robot_service: Annotated[RobotService, Depends(RobotService)], robot_id: str) -> Robot:
    return robot_service.get_robot_by_id(robot_id)


@router.post("/create", response_model=RobotOutput)
def create_robot(
    robot_service: Annotated[RobotService, Depends(RobotService)],
    robot: RobotInput
) -> Robot:
    return robot_service.create_robot(robot)



@router.post("/send_command")
def send_command(
    ipc: Annotated[Subject, Depends(create_subject)],
    command: RobotCommand
):
    ipc.on_next(command)
    return {"message": "Command sent"}
