from typing import Annotated
from uuid import UUID

from aioreactive import AsyncSubject
from fastapi import Depends

from .json_rpc_commands import RobotCommand

_ipc: AsyncSubject | None = None


def create_subject() -> AsyncSubject:
    global _ipc

    if _ipc is None:
        print("Creating subject")
        _ipc = AsyncSubject()

    return _ipc


class UserRobotComunication:
    def __init__(self, ipc: AsyncSubject, robot_id: UUID | None = None):
        self.ipc = ipc
        self.robot_id = robot_id

    def set_robot_id(self, robot_id: UUID | None):
        self.robot_id = robot_id
        return self

    async def send_command(self, command: RobotCommand):
        print("Command ", command)
        print("Robot id ", self.robot_id)
        await self.ipc.asend(command)


def create_user_robot_communication(
        ipc: Annotated[AsyncSubject, Depends(create_subject)]
) -> UserRobotComunication:
    return UserRobotComunication(ipc)


RobotIPCDep = Annotated[UserRobotComunication, Depends(create_user_robot_communication)]
