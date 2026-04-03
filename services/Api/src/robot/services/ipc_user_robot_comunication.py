"""Comunicación usuario ↔ robot vía RosBridge.

El usuario se conecta por WebSocket a la API, se autentica, y envía
comandos JSON-RPC. La API los publica al topic ROS del robot vía rosbridge
y rutea las respuestas de vuelta al usuario.
"""

import asyncio
import logging
from typing import Annotated, final
import functools

from fastapi import Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..entities.errors import SerializableException, UserValidationTimeoutException
from ..entities.json_rpc_commands import UserWsAuthentication
from .robot_service import RobotServiceDep, RobotService
from .access_validator import AccessValidator
from .rosbridge_client import RosBridgeClient, RosBridgeClientDep
from ..entities import Robot
from ..repositories.robot_connection import RobotConnectionRepository, RobotConnectionRepositoryDep
from ..adapters import UserStreamSource, RobotScopedStreamSource
from ...auth.entities import User
from ...auth.services import UserService, UserServiceDep


logger = logging.getLogger(__name__)


@final
class UserToRobotComunication:
    """Gestiona la comunicación WebSocket de un usuario con robots vía RosBridge."""

    def __init__(self,
        robot_service: RobotService,
        access_validator: AccessValidator,
        robot_connection_repository: RobotConnectionRepository,
        user_service: UserService,
        rosbridge: RosBridgeClient,
    ):
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.robot_connection_repository = robot_connection_repository
        self.user_service = user_service
        self.rosbridge = rosbridge

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        user = None
        try:

            user, robot = await self._validate_user_session(websocket)

            userConnection = self.robot_connection_repository.addUserConnection(
                user,
                UserStreamSource(websocket)
            )

            robotConnection = self.robot_connection_repository.getRobotConnection(robot)

            if robotConnection is None:
                robotConnection = self.robot_connection_repository.addRobotConnection(
                    robot,
                    RobotScopedStreamSource(self.rosbridge, robot)
                )

            bidirectionalPipe = self.robot_connection_repository.addUserXRobotConnection(userConnection, robotConnection)

            await bidirectionalPipe.connect()

        except WebSocketDisconnect:
            print("Client disconnected")
        except SerializableException as e:
            print(f"SerializableException {e.to_dict()}")
            await websocket.send_json(e.to_jsonrpc())
            await websocket.close()
        except ExceptionGroup as eg:
            for exc in eg.exceptions:
                logger.error(f"TaskGroup sub-exception: {exc}", exc_info=exc)
            await websocket.send_json({"status": "error", "message": "Internal Server Error"})
            await websocket.close()
        except Exception as e:
            logger.error(f"Exception {e}", exc_info=e)
            await websocket.send_json({"status": "error", "message": "Internal Server Error"})
            await websocket.close()
        finally:
            if user is not None:
                self.robot_connection_repository.discardUserConnection(user, discardPipeddConnections=True)

    async def _validate_user_session(self, websocket: WebSocket) -> tuple[User, Robot]:
        try:

            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)  # pyright: ignore[reportAny]

            entity = UserWsAuthentication.model_validate(result)

            # user_session = self.access_validator.create_robot_access_session(entity)

            user = self.user_service.get_user_by_token(entity.token)
            robot = self.robot_service.get_robot_by_id(entity.robot_id)

            if user is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            if robot is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            # self.access_validator.validate_grant_access(entity.token, entity.robot_id, None)

            await websocket.send_json({"message": "success auth"})

            return user, robot

        except asyncio.TimeoutError as e:
            logger.error(e)
            raise UserValidationTimeoutException() from e


@functools.cache
def create_user_robot_communication(
        rosbridge: RosBridgeClientDep,
        robot_service: RobotServiceDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
        robot_connection_repository: RobotConnectionRepositoryDep,
        user_service: UserServiceDep
) -> UserToRobotComunication:
    return UserToRobotComunication(
        robot_service,
        access_validator,
        robot_connection_repository,
        user_service,
        rosbridge
    )


RobotIPCDep = Annotated[UserToRobotComunication, Depends(create_user_robot_communication)]
