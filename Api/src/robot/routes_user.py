from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path, Body, HTTPException
from fastapi.params import Depends
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from .access_validator import AccessValidator
from .robot import RobotCommand
from .robot.ipc_user_robot_comunication import RobotIPCDep
from .robot.json_rpc_commands import RRobotCommand, RobotCommandExtended
from .robot.robot_service import RobotServiceDep
from ..auth.services.encryption import TokenStrDep

router = APIRouter(tags=["robots", "user"])

def _check_robot_existence(
    robot_id: Annotated[str, Path()],
    robot_service: RobotServiceDep
) -> None:
    try:
        if not robot_service.exists_robot(robot_id):
            raise HTTPException(status_code=404, detail="Robot not found")
    except:
        raise HTTPException(status_code=404, detail="Robot not found")


def _check_user_access(
    access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
    user_token: TokenStrDep,
    robot_id: Annotated[UUID, Path()],
) -> None:
    if not access_validator.grant_access(user_token, robot_id):
        raise HTTPException(403, "User doesn't has access to robot")



@router.post("/send_command/{robot_id}", dependencies=[Depends(_check_robot_existence), Depends(_check_user_access)])
def send_command(
        robot_id: Annotated[UUID, Path()],
        ipc: RobotIPCDep,
        command_data: RRobotCommand
):
    ipc.set_robot_id(robot_id).send_command(RobotCommand(robot_id=robot_id, args=command_data))

    return {"message": "Command sent"}


@router.websocket("/send_command")
async def send_command_ws(
        websocket: WebSocket,
        ipc: RobotIPCDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
        robot_service: RobotServiceDep
):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            try:
                payload = RobotCommandExtended(**data)

                if not robot_service.exists_robot(payload.robot_id):
                    await websocket.send_json({"status": "error", "message": f"robot doesn't exist"})

                if not access_validator.grant_access(payload.access_token, payload.robot_id):
                    await websocket.send_json({"status": "error", "message": f"user doesn't have access to this robot"})

                await ipc.send_command(RobotCommand(robot_id=payload.robot_id, args=payload))

            except ValidationError as e:
                await websocket.send_json({"status": "error", "message": f"Invalid payload: {e.errors()}"})

    except WebSocketDisconnect:
        print("Client disconnected")
    except:
        await websocket.send_json({"status": "error", "message": "unknown error"})
        await websocket.close()
