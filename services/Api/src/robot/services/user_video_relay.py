"""Relay de video usuario↔robot: canal WS separado del pipe de comandos.

Ver docs/superpowers/specs/2026-08-20-camera-video-webclient-design.md.
Valida el mismo token robot_access que /user/robot/send_command (mismo
control de acceso), pero no pasa por UsersXRobotMapType — es push-only,
sin heartbeat propio. Si el socket muere, el browser reconecta directo,
sin necesitar avisar al pipe de comandos.
"""

import asyncio
import functools
import logging
from typing import Annotated, final

from fastapi import Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..entities.errors import UserValidationTimeoutException
from ..entities.json_rpc_commands import UserWsAuthentication
from ..repositories.video_relay import VideoRelayRepository, VideoRelayRepositoryDep
from .access_validator import AccessValidator, UserRobotAccessSession
from .robot_service import RobotService, RobotServiceDep
from ...auth.services import UserService, UserServiceDep

logger = logging.getLogger(__name__)


@final
class UserVideoRelay:
    def __init__(
        self,
        robot_service: RobotService,
        access_validator: AccessValidator,
        video_relay_repository: VideoRelayRepository,
        user_service: UserService,
    ):
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.video_relay_repository = video_relay_repository
        self.user_service = user_service

    async def connect_ws(self, websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny]
            entity = UserWsAuthentication.model_validate(result)

            user = self.user_service.get_user_by_token(entity.token)
            robot = self.robot_service.get_robot_by_id(entity.robot_id)
            if user is None or robot is None:
                raise UserValidationTimeoutException()

            self.access_validator.validate_grant_access(
                entity.token, entity.robot_id, UserRobotAccessSession(user.usr_name),
            )

            await websocket.send_json({"message": "success auth"})

            relay = self.video_relay_repository.get_or_create(str(robot.id))
            while True:
                frame = await relay.next_frame()
                await websocket.send_bytes(frame)

        except (WebSocketDisconnect, asyncio.TimeoutError):
            logger.info("Conexión de video de usuario cerrada")
        except Exception as e:
            logger.error("Error en video de usuario: %s", e, exc_info=e)
            try:
                await websocket.close()
            except Exception:
                pass


@functools.cache
def create_user_video_relay(
    robot_service: RobotServiceDep,
    access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
    video_relay_repository: VideoRelayRepositoryDep,
    user_service: UserServiceDep,
) -> UserVideoRelay:
    return UserVideoRelay(robot_service, access_validator, video_relay_repository, user_service)


UserVideoRelayDep = Annotated[UserVideoRelay, Depends(create_user_video_relay)]
