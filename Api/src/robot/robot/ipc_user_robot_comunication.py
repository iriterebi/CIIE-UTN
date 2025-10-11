import asyncio
import logging
from datetime import datetime
from typing import Annotated

from aioreactive import AsyncSubject
from fastapi import Depends
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect

from .errors import SerializableException, RobotAccessException, UserValidationTimeoutException
from .json_rpc_commands import RobotCommand, RobotCommandExtended, UserWsAuthentication
from .robot_service import RobotServiceDep, RobotService
from ..access_validator import AccessValidator, UserRobotAccessSession

type IPC_Subject = AsyncSubject

_ipc: IPC_Subject | None = None

#
# # Create a logger instance
# logger = logging.getLogger(__name__)
# #logger.setLevel(logging.NOTSET) # Set the desired logging level
#
# # Create a console handler and formatter
# handler = logging.StreamHandler()
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)
#

def create_subject() -> IPC_Subject:
    global _ipc

    if _ipc is None:
        print("Creating subject")
        _ipc = AsyncSubject()

    return _ipc


class UserToRobotCommunication:
    user_session: UserRobotAccessSession | None

    def __init__(self, ipc: IPC_Subject, robot_service: RobotService, access_validator: AccessValidator):
        self.ipc = ipc
        self.robot_service = robot_service
        self.access_validator = access_validator

    async def _send_command_to_robot(self, command: RobotCommand):
        print("Command ", command)
        await self.ipc.asend(command)

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        try:
            await self._validate_user(websocket)

            async with asyncio.TaskGroup() as tg:
                # TODO: buscar manera de hacer correr keep_user_session
                # tg.create_task(self.keep_user_session(websocket))
                tg.create_task(self.receive_user_commands(websocket))
                tg.create_task(self.receive_robot_feedback(websocket))

        except WebSocketDisconnect:
            print("Client disconnected")
        except SerializableException as e:
            print(f"SerializableException {e.to_dict()}",)
            await websocket.send_json(e.to_jsonrpc())
            await websocket.close()
        except Exception as e:
            print(f"Exception {e}")
            await websocket.send_json({"status": "error", "message": e})
            await websocket.close()

    async def _validate_user(self, websocket: WebSocket) -> None:
        try:
            # wait for auth
            result = await asyncio.wait_for(websocket.receive_json(), timeout=10)
            self.user_session = self.access_validator.create_robot_access_session(UserWsAuthentication(**result))

            await websocket.send_json({"message": "success auth"})

        except asyncio.TimeoutError as e:
            raise UserValidationTimeoutException() from e

    async def keep_user_session(self, websocket: WebSocket):
        if self.user_session is None:
            await self._validate_user(websocket)

        while True:
            delta = (self.user_session.expiration_time - datetime.now()).total_seconds()

            await asyncio.sleep(delta - 12)

            # faltan 12 segundos para que la sessión expire
            # se solicita reautenticación (esto debe ser hecho automáticamente por el frontend)
            await websocket.send_json({"message": "user session expiration soon", "code": "SessionExpirationSoon"})

            await self._validate_user(websocket)

    async def receive_user_commands(self, websocket: WebSocket):
        while True:
            await self._receive_user_command(websocket)

    async def _receive_user_command(self, websocket: WebSocket):
        try:
            data = await websocket.receive_json()

            payload = RobotCommandExtended(**data)
            print(f"RobotCommandExtended {payload.model_dump()}")

            self.robot_service.validate_exists_robot(payload.robot_id)

            # if not self.access_validator.grant_access(payload.access_token, payload.robot_id, self.user_session):
            #     await websocket.send_json({
            #         "status": "error",
            #         "message": f"user doesn't have access to this robot"
            #     })

            self.access_validator.validate_grant_access(payload.access_token, payload.robot_id, self.user_session)

            await self._send_command_to_robot(RobotCommand(robot_id=payload.robot_id, args=payload))

        except ValidationError as e:
            await websocket.send_json({"status": "error", "message": f"Invalid payload: {e.errors()}"})

        except SerializableException as e:
            await websocket.send_json(e.to_jsonrpc())

    async def receive_robot_feedback(self, websocket: WebSocket):
        # TODO: obtener la respuesta del robot
        pass


def create_user_robot_communication(
        ipc: Annotated[AsyncSubject, Depends(create_subject)],
        robot_service: RobotServiceDep,
        access_validator: Annotated[AccessValidator, Depends(AccessValidator)],
) -> UserToRobotCommunication:
    return UserToRobotCommunication(ipc, robot_service, access_validator)


RobotIPCDep = Annotated[UserToRobotCommunication, Depends(create_user_robot_communication)]
