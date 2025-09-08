from typing import Iterable
from fastapi import WebSocket, WebSocketDisconnect
from reactivex.operators import filter as rx_filter, observe_on
from reactivex.subject import Subject
from reactivex.abc import DisposableBase
from reactivex.disposable import CompositeDisposable, Disposable
from reactivex import from_iterable
from reactivex.scheduler.eventloop import AsyncIOThreadSafeScheduler, AsyncIOScheduler
import asyncio

from .json_rpc_commands import RobotCommand, RobotResponse
from .robot_service import RobotService
from .robot import Robot


class RobotConnection:
    websocket: WebSocket | None = None
    observer: Subject
    service: RobotService
    robot: Robot
    disposable: DisposableBase | None = None

    def __init__(self, ipc: Subject, service: RobotService, robot: Robot):
        self.observer = ipc
        self.service = service
        self.robot = robot

    async def connect(self, websocket: WebSocket):
        self.websocket = websocket
        await websocket.accept()

        loop = asyncio.get_event_loop()

        self.disposable = CompositeDisposable()

        self.disposable.add(
            self.observer.pipe(
                observe_on(scheduler=AsyncIOThreadSafeScheduler(loop=loop)),
                rx_filter(lambda x: x.robot_id == self.robot.id)
            ).subscribe(self.send, scheduler=AsyncIOScheduler(loop=loop))
        )

        self.disposable.add(
            # TODO: no funciona con asyncio
            from_iterable(self.iter_response()).subscribe(
                self.observer.on_next, scheduler=AsyncIOScheduler(loop=loop))
        )

        future = asyncio.Future(loop = loop)

        self.disposable.add(
            Disposable(lambda: future.set_result(None))
        )

        return future

    def disconnect(self):
        self.disposable.dispose()
        self.websocket = None

    async def send(self, data: RobotCommand):
        await self.websocket.send_text(data.model_dump_json())

    async def receive(self) -> RobotResponse:
        data = await self.websocket.receive_json()
        return RobotResponse(**data)

    async def iter_response(self) -> Iterable[RobotResponse]:
        try:
            while True:
                yield await self.receive()
        except WebSocketDisconnect:
            pass
