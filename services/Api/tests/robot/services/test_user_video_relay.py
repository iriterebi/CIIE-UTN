import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

from src.robot.entities import Robot
from src.robot.entities.errors import RobotAccessException
from src.robot.repositories.video_relay import VideoRelayRepository
from src.robot.services.access_validator import AccessValidator
from src.robot.services.user_video_relay import UserVideoRelay
from src.auth.entities import User


def _make_robot():
    r = MagicMock(spec=Robot)
    r.id = uuid4()
    return r


def _make_user():
    u = MagicMock(spec=User)
    u.usr_name = "juan"
    return u


class _FakeWebSocket:
    def __init__(self, incoming, *, stop_after: int = 999):
        self._incoming = incoming
        self._stop_after = stop_after
        self.sent_json = []
        self.sent_bytes = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        return self._incoming

    async def send_json(self, data):
        self.sent_json.append(data)

    async def send_bytes(self, data):
        self.sent_bytes.append(data)
        if len(self.sent_bytes) >= self._stop_after:
            raise ConnectionError("simulated client disconnect")

    async def close(self):
        self.closed = True


def _make_relay_service(robot, *, grant_access=True):
    robot_service = MagicMock()
    robot_service.get_robot_by_id.return_value = robot

    user_service = MagicMock()
    user_service.get_user_by_token.return_value = _make_user()

    access_validator = MagicMock(spec=AccessValidator)
    if grant_access:
        access_validator.validate_grant_access.return_value = None
    else:
        access_validator.validate_grant_access.side_effect = RobotAccessException(str(robot.id))

    video_relay_repository = VideoRelayRepository()

    service = UserVideoRelay(robot_service, access_validator, video_relay_repository, user_service)
    return service, video_relay_repository


class TestUserVideoRelayConnectWs:
    def test_reenvia_frames_del_relay_hasta_que_el_cliente_se_va(self):
        robot = _make_robot()
        service, repo = _make_relay_service(robot)
        ws = _FakeWebSocket({"token": "tok", "robot_id": str(robot.id)}, stop_after=2)

        async def run():
            relay = repo.get_or_create(str(robot.id))

            async def push_frames():
                await asyncio.sleep(0.01)  # Let connect_ws start
                relay.push_frame(b"frame1")
                await asyncio.sleep(0.01)
                relay.push_frame(b"frame2")

            pusher = asyncio.create_task(push_frames())
            await service.connect_ws(ws)
            await pusher

        asyncio.run(run())

        assert ws.accepted is True
        assert {"message": "success auth"} in ws.sent_json
        assert ws.sent_bytes == [b"frame1", b"frame2"]

    def test_sin_grant_access_no_reenvia_frames(self):
        robot = _make_robot()
        service, repo = _make_relay_service(robot, grant_access=False)
        ws = _FakeWebSocket({"token": "tok", "robot_id": str(robot.id)})

        async def run():
            await service.connect_ws(ws)

        asyncio.run(run())

        assert ws.sent_bytes == []
        assert {"message": "success auth"} not in ws.sent_json
