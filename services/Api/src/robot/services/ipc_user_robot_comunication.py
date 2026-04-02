"""Comunicación usuario ↔ robot vía RosBridge.

El usuario se conecta por WebSocket a la API, se autentica, y envía
comandos JSON-RPC. La API los publica al topic ROS del robot vía rosbridge
y rutea las respuestas de vuelta al usuario.
"""

import asyncio
import logging
from typing import Annotated, Any, final, override
import functools
import json

from fastapi import Depends
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from ..entities.errors import SerializableException, UserValidationTimeoutException
from ..entities.json_rpc_commands import RRobotCommand, UserWsAuthentication
from .robot_service import RobotServiceDep, RobotService
from .access_validator import AccessValidator
from .rosbridge_client import RosBridgeClient, RosBridgeClientDep
from ..entities import Robot
from ..repositories.robot_connection import RobotConnectionRepository, RobotConnectionRepositoryDep, StreamSource
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
                UserToRobotComunication.UserStreamSource(websocket)
            )

            robotConnection = self.robot_connection_repository.getRobotConnection(robot)

            if robotConnection is None:
                robotConnection = self.robot_connection_repository.addRobotConnection(
                    robot,
                    UserToRobotComunication.RobotScopedStreamSource(self.rosbridge, robot)
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

    @final
    class UserStreamSource(StreamSource):
        # TODO: manejar cuestiones relacionadas a la sesión del usuario (ejemplo: expiración)
        # TODO: validación profunda del payload — ampliar más allá de RRobotCommand
        # TODO: verificación del access_token per-sesión
        def __init__(self, websocket: WebSocket):
            self.websocket = websocket

        @override
        async def accept(self):
            if self.websocket.application_state != WebSocketState.CONNECTED:
                return await self.websocket.accept()

        @override
        async def disconnect(self):
            return await self.websocket.close()

        @override
        async def receive_bytes(self) -> bytes:
            while True:
                try:
                    text = await self.websocket.receive_text()
                    command = RRobotCommand.model_validate_json(text)
                    return command.model_dump_json().encode()
                except ValidationError as e:
                    logger.error(f"Payload validation error: {e}")
                    await self.websocket.send_json({
                        "status": "error",
                        "message": f"Invalid payload: {e.errors()}"
                    })
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON: {e}")
                    await self.websocket.send_json({
                        "status": "error",
                        "message": f"Invalid JSON: {e}"
                    })

        @override
        async def send_bytes(self, data: bytes):
            await self.websocket.send_text(data.decode())

    class RobotScopedStreamSource(StreamSource):
        def __init__(self, rosbridge: RosBridgeClient, robot: Robot):
            self.rosbridge: RosBridgeClient = rosbridge
            self.robot: Robot = robot
            self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
            self._idle: bool = True

        @override
        async def accept(self):
            """Suscribirse a los topics ROS del robot via rosbridge."""
            await self.rosbridge.subscribe_robot(self.robot, self.queue)

        @override
        async def disconnect(self):
            """Desuscribirse de los topics ROS del robot."""
            await self.rosbridge.unsubscribe_robot(self.robot, self.queue)

        async def on_idle_changed(self, idle: bool):
            self._idle = idle
            if idle:
                # Descartar mensajes acumulados que nadie va a leer
                while not self.queue.empty():
                    _ = self.queue.get_nowait()


        @override
        async def receive_bytes(self) -> bytes:
            """Esperar respuesta del robot desde ROS, retornar como bytes."""
            response = await self.queue.get()
            return json.dumps(response).encode()

        @override
        async def send_bytes(self, data: bytes):
            """Publicar comando al topic ROS del robot via rosbridge."""
            payload: dict[str, Any] = json.loads(data)
            await self.rosbridge.publish_command(self.robot, payload)



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
