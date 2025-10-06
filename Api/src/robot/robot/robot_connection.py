import aioreactive as arx
from aioreactive import AsyncSubject
from expression import pipe
from expression.system import AsyncDisposable
from fastapi import WebSocket

from .json_rpc_commands import RobotCommand, RobotResponse
from .robot import Robot
from .robot_service import RobotService


class RobotConnection:
    websocket: WebSocket | None = None
    observer: AsyncSubject
    service: RobotService
    robot: Robot
    disposable: AsyncDisposable | None = None
    adisposable: AsyncDisposable | None = None

    def __init__(self, ipc: AsyncSubject, service: RobotService, robot: Robot):
        self.observer = ipc
        self.service = service
        self.robot = robot
        print("robot", robot)

    async def connect(self, websocket: WebSocket):
        self.websocket = websocket
        await websocket.accept()

        self.disposable = await (pipe(
            self.observer,
            arx.filter(lambda x: x.robot_id == self.robot.id)
        ).subscribe_async(self.send))

        while True:
            await self._emit_response(await self.receive())

    async def disconnect(self):
        self.disposable.dispose()
        await self.adisposable.dispose_async()
        self.websocket = None

    async def send(self, data: RobotCommand):
        print("send", data)
        await self.websocket.send_text(data.model_dump_json())

    async def receive(self) -> RobotResponse:
        data = await self.websocket.receive_json()
        print("receive", data)
        return RobotResponse(**data)

    async def _emit_response(self, response: RobotResponse):
        await self.observer.asend(response)
