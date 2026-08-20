from fastapi import APIRouter
from starlette.websockets import WebSocket

from ..services.ipc_user_robot_comunication import RobotIPCDep
from ..services.user_video_relay import UserVideoRelayDep

router = APIRouter(tags=["robots", "user"])


@router.websocket("/send_command")
async def send_command_ws(
        websocket: WebSocket,
        ipc: RobotIPCDep,
):
    await ipc.connect_ws(websocket)


@router.websocket("/video")
async def video_ws(
        websocket: WebSocket,
        video_relay: UserVideoRelayDep,
):
    await video_relay.connect_ws(websocket)
