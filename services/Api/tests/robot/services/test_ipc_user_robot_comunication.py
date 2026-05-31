import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.robot.entities.errors import RobotAccessException
from src.robot.services.access_validator import AccessValidator
from src.robot.services.ipc_user_robot_comunication import UserToRobotComunication


@pytest.fixture
def encryption_service():
    return MagicMock()


@pytest.fixture
def access_validator(encryption_service):
    return AccessValidator(encryption_service)


@pytest.fixture
def user():
    u = MagicMock()
    u.usr_name = "userA"
    return u


@pytest.fixture
def robot():
    r = MagicMock()
    r.id = uuid4()
    return r


@pytest.fixture
def orchestrator(access_validator, user, robot):
    user_service = MagicMock()
    user_service.get_user_by_token.return_value = user

    robot_service = MagicMock()
    robot_service.get_robot_by_id.return_value = robot

    return UserToRobotComunication(
        robot_service=robot_service,
        access_validator=access_validator,
        robot_connection_repository=MagicMock(),
        user_service=user_service,
    )


def _make_ws(auth_payload: dict):
    ws = AsyncMock()
    ws.receive_json.return_value = auth_payload
    return ws


class TestValidateUserSessionAuthorization:
    def test_login_token_sin_type_robot_access_bloqueado(
        self, orchestrator, encryption_service, robot
    ):
        # token de login normal: tiene sub/role pero no type=robot_access
        encryption_service.decode_token.return_value = {
            "sub": "userA",
            "role": "alumno",
        }
        ws = _make_ws({"token": "login-token", "robot_id": str(robot.id)})

        with pytest.raises(RobotAccessException):
            asyncio.run(orchestrator._validate_user_session(ws))

    def test_robot_access_token_con_robot_id_distinto_bloqueado(
        self, orchestrator, encryption_service, robot
    ):
        otro_robot = uuid4()
        # token válido para otro_robot, pero el WS pide robot.id
        encryption_service.decode_token.return_value = {
            "sub": "userA",
            "type": "robot_access",
            "robot_id": str(otro_robot),
        }
        ws = _make_ws({"token": "robot-access-token", "robot_id": str(robot.id)})

        with pytest.raises(RobotAccessException):
            asyncio.run(orchestrator._validate_user_session(ws))

    def test_robot_access_token_coincidente_permite_paso(
        self, orchestrator, encryption_service, robot, user
    ):
        encryption_service.decode_token.return_value = {
            "sub": "userA",
            "type": "robot_access",
            "robot_id": str(robot.id),
        }
        ws = _make_ws({"token": "robot-access-token", "robot_id": str(robot.id)})

        result_user, result_robot = asyncio.run(
            orchestrator._validate_user_session(ws)
        )

        assert result_user is user
        assert result_robot is robot
        ws.send_json.assert_awaited_once_with({"message": "success auth"})
