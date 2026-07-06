"""Comunicación usuario ↔ robot vía WebSocket directo.

El usuario se conecta por WebSocket a la API, se autentica, y envía
comandos JSON-RPC. La API enruta cada mensaje hacia el WebSocket de la
Pi del robot a través del pipe `UsersXRobotMapType` (ver
`RobotConnection` / `UserConnection`) y devuelve las respuestas por el
mismo camino.
"""

import asyncio
import logging
from typing import Annotated, final
import functools

from fastapi import Depends
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..entities.errors import (
    JSONRPC_INTERNAL_ERROR,
    SerializableException,
    UserValidationTimeoutException,
    serialise_as_jsonrpc_error,
)
from ..entities.json_rpc_commands import UserWsAuthentication
from ..utils.heartbeat import HeartbeatTimeoutError, run_heartbeat_watchdog
from .robot_service import RobotServiceDep, RobotService
from .access_validator import AccessValidator, UserRobotAccessSession
from ..entities import Robot
from ..repositories.robot_connection import RobotConnectionRepository, RobotConnectionRepositoryDep
from ..repositories.stream_entities import RobotSideClosed, UserSideClosed
from ..adapters import UserStreamSource
from ...auth.entities import User
from ...auth.services import UserService, UserServiceDep


logger = logging.getLogger(__name__)

class RobotConnectionNotFound(Exception):
    def __init__(self, robot: Robot) -> None:
        super().__init__("Robot is Disconnected")
        self.robot = robot



@final
class UserToRobotComunication:
    """Gestiona la comunicación WebSocket de un usuario con su robot a través de la API."""

    def __init__(self,
        robot_service: RobotService,
        access_validator: AccessValidator,
        robot_connection_repository: RobotConnectionRepository,
        user_service: UserService,
    ):
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.robot_connection_repository = robot_connection_repository
        self.user_service = user_service

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        user = None
        try:
            logger.info("validating user")
            user, robot = await self._validate_user_session(websocket)

            logger.info("establishing user connection")
            pong_received = asyncio.Event()
            pong_received.set()
            userStreamSource = UserStreamSource(websocket, pong_received=pong_received)
            userConnection = self.robot_connection_repository.addUserConnection(
                user,
                userStreamSource
            )

            logger.info("obtaining robot connection")
            robotConnection = self.robot_connection_repository.getRobotConnection(robot)

            if robotConnection is None:
                raise RobotConnectionNotFound(robot)

            logger.info("creating User-robot comunication pipe")
            bidirectionalPipe = self.robot_connection_repository.addUserXRobotConnection(userConnection, robotConnection)

            async def _send_ping() -> None:
                await userStreamSource.send_control({"type": "ping"})

            async def _watch_heartbeat() -> None:
                try:
                    await run_heartbeat_watchdog(_send_ping, pong_received)
                except HeartbeatTimeoutError:
                    logger.warning("Heartbeat del usuario expiró, cerrando conexión")
                    await websocket.close()

            logger.info("connecting pipe")
            try:
                async with asyncio.TaskGroup() as tg:
                    tg.create_task(_watch_heartbeat())
                    tg.create_task(bidirectionalPipe.connect(
                        wait_for_robot_reconnect=self.robot_connection_repository.wait_for_robot_reconnect,
                    ))
            except* UserSideClosed:
                logger.info("user closed websocket, ending session")
            except* RobotSideClosed:
                logger.info("robot no reconectó a tiempo, cerrando sesión de usuario")

        except WebSocketDisconnect:
            logger.info("Client disconnected")
        except SerializableException as e:
            logger.warning("SerializableException: %s", e.to_dict())
            await websocket.send_json(
                serialise_as_jsonrpc_error(e, message_id=None, code=JSONRPC_INTERNAL_ERROR)
            )
            await websocket.close()
        except ExceptionGroup as eg:
            logger.error("connect user ws error:")
            for exc in eg.exceptions:
                logger.error(f"TaskGroup sub-exception: {exc}", exc_info=exc)
            await websocket.send_json({"status": "error", "message": "Internal Server Error"})
            await websocket.close()
        except RobotConnectionNotFound as e:
            await websocket.send_json({"status": "error", "message": "Robot is Disconnected"})
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

            user = self.user_service.get_user_by_token(entity.token)
            robot = self.robot_service.get_robot_by_id(entity.robot_id)

            if user is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            if robot is None:
                # TODO: lanzar un mejor error
                raise UserValidationTimeoutException()

            self.access_validator.validate_grant_access(
                entity.token,
                entity.robot_id,
                UserRobotAccessSession(user.usr_name),
            )

            await websocket.send_json({"message": "success auth"})

            return user, robot

        except asyncio.TimeoutError as e:
            logger.error(e)
            raise UserValidationTimeoutException() from e


@functools.cache
def create_user_robot_communication(
        robot_service: RobotServiceDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
        robot_connection_repository: RobotConnectionRepositoryDep,
        user_service: UserServiceDep
) -> UserToRobotComunication:
    return UserToRobotComunication(
        robot_service,
        access_validator,
        robot_connection_repository,
        user_service
    )


RobotIPCDep = Annotated[UserToRobotComunication, Depends(create_user_robot_communication)]
