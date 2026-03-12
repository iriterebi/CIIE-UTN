"""Comunicación usuario ↔ robot vía RosBridge.

El usuario se conecta por WebSocket a la API, se autentica, y envía
comandos JSON-RPC. La API los publica al topic ROS del robot vía rosbridge
y rutea las respuestas de vuelta al usuario.
"""

import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from .errors import SerializableException, RobotAccessException, UserValidationTimeoutException
from .json_rpc_commands import RobotCommand, RobotCommandExtended, UserWsAuthentication
from .robot_service import RobotServiceDep, RobotService
from ..access_validator import AccessValidator, UserRobotAccessSession
from ..rosbridge_client import RosBridgeClient, RosBridgeClientDep

logger = logging.getLogger(__name__)


class UserToRobotCommunication:
    """Gestiona la comunicación WebSocket de un usuario con robots vía RosBridge."""

    user_session: UserRobotAccessSession | None

    def __init__(self, rosbridge: RosBridgeClient, robot_service: RobotService, access_validator: AccessValidator):
        self.rosbridge = rosbridge
        self.robot_service = robot_service
        self.access_validator = access_validator
        self.response_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._subscribed_robots: set[UUID] = set()

    async def _send_command_to_robot(self, command: RobotCommand):
        """Publica un comando al topic ROS del robot vía rosbridge."""
        print("Command ", command)
        await self.rosbridge.publish_command(
            command.robot_id,
            command.args.model_dump(),
        )

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        try:
            await self._validate_user(websocket)

            async with asyncio.TaskGroup() as tg:
                tg.create_task(self.receive_user_commands(websocket))
                tg.create_task(self.receive_robot_feedback(websocket))

        except WebSocketDisconnect:
            print("Client disconnected")
        except SerializableException as e:
            print(f"SerializableException {e.to_dict()}")
            await websocket.send_json(e.to_jsonrpc())
            await websocket.close()
        except Exception as e:
            print(f"Exception {e}")
            await websocket.send_json({"status": "error", "message": str(e)})
            await websocket.close()
        finally:
            await self._cleanup()

    async def _validate_user(self, websocket: WebSocket) -> None:
        try:
            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            self.user_session = self.access_validator.create_robot_access_session(UserWsAuthentication(**result))

            await websocket.send_json({"message": "success auth"})

        except asyncio.TimeoutError as e:
            raise UserValidationTimeoutException() from e

    async def receive_user_commands(self, websocket: WebSocket):
        while True:
            await self._receive_user_command(websocket)

    async def _receive_user_command(self, websocket: WebSocket):
        try:
            data = await websocket.receive_json()

            payload = RobotCommandExtended(**data)
            print(f"RobotCommandExtended {payload.model_dump()}")

            self.robot_service.validate_exists_robot(payload.robot_id)

            self.access_validator.validate_grant_access(payload.access_token, payload.robot_id, self.user_session)

            # Suscribirse al robot si es la primera vez
            await self._ensure_robot_subscription(payload.robot_id)

            await self._send_command_to_robot(RobotCommand(robot_id=payload.robot_id, args=payload))

        except ValidationError as e:
            await websocket.send_json({"status": "error", "message": f"Invalid payload: {e.errors()}"})

        except SerializableException as e:
            await websocket.send_json(e.to_jsonrpc())

    async def receive_robot_feedback(self, websocket: WebSocket):
        """Lee respuestas de robots desde la queue y las envía al usuario."""
        while True:
            response = await self.response_queue.get()
            await websocket.send_json(response)

    async def _ensure_robot_subscription(self, robot_id: UUID):
        """Suscribe la queue a un robot si aún no lo estamos."""
        if robot_id not in self._subscribed_robots:
            await self.rosbridge.subscribe_robot(robot_id, self.response_queue)
            self._subscribed_robots.add(robot_id)

    async def _cleanup(self):
        """Desuscribir de todos los robots al desconectar."""
        for robot_id in self._subscribed_robots:
            await self.rosbridge.unsubscribe_robot(robot_id, self.response_queue)
        self._subscribed_robots.clear()


def create_user_robot_communication(
        rosbridge: RosBridgeClientDep,
        robot_service: RobotServiceDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
) -> UserToRobotCommunication:
    return UserToRobotCommunication(rosbridge, robot_service, access_validator)


RobotIPCDep = Annotated[UserToRobotCommunication, Depends(create_user_robot_communication)]
