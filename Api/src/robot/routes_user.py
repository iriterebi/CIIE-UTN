from fastapi import APIRouter
from starlette.websockets import WebSocket

from .robot.ipc_user_robot_comunication import RobotIPCDep

router = APIRouter(tags=["robots", "user"])


@router.websocket("/send_command")
async def send_command_ws(
        websocket: WebSocket,
        ipc: RobotIPCDep,
):
    await ipc.connect_ws(websocket)
