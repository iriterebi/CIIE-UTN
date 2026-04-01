from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from src.robot.services.handshake_service import HandshakeService
from src.robot.entities.robot import RobotStatus
from src.auth.entities.access_token import AccessToken


def _make_robot(status=RobotStatus.APPROVED, psw="hashed"):
    robot = MagicMock()
    robot.id = uuid4()
    robot.external_identifier = str(uuid4())
    robot.status = status
    robot.psw = psw
    return robot


def _make_credentials(username="ext-id", password="password"):
    return HTTPBasicCredentials(username=username, password=password)


@pytest.fixture
def encryption_service():
    mock = MagicMock()
    mock.verify_pwd.return_value = True
    mock.create_bearer_access_token.return_value = AccessToken(
        access_token="jwt-token",
        token_type="bearer",
        scope="broker:report_log broker:listen_commands",
        expires_in=1800,
    )
    return mock


@pytest.fixture
def robot_service():
    return MagicMock()


@pytest.fixture
def service(encryption_service, robot_service):
    return HandshakeService(encryption_service, robot_service)


class TestCreateAccessTokenByBasicCredentials:
    def test_handshake_exitoso(self, service, robot_service, encryption_service):
        robot = _make_robot()
        robot_service.get_robot_by_external_identifier.return_value = robot
        credentials = _make_credentials()

        token, returned_robot = service.create_access_token_by_basic_credentials(credentials)

        assert isinstance(token, AccessToken)
        assert returned_robot == robot
        encryption_service.verify_pwd.assert_called_once()

    def test_robot_no_encontrado_lanza_400(self, service, robot_service):
        robot_service.get_robot_by_external_identifier.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            service.create_access_token_by_basic_credentials(_make_credentials())

        assert exc_info.value.status_code == 400
        assert "username" in exc_info.value.detail.lower()

    def test_password_incorrecto_lanza_400(self, service, robot_service, encryption_service):
        robot = _make_robot()
        robot_service.get_robot_by_external_identifier.return_value = robot
        encryption_service.verify_pwd.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            service.create_access_token_by_basic_credentials(_make_credentials())

        assert exc_info.value.status_code == 400
        assert "password" in exc_info.value.detail.lower()

    def test_robot_no_aprobado_lanza_403(self, service, robot_service):
        robot = _make_robot(status=RobotStatus.PENDING_APPROVAL)
        robot_service.get_robot_by_external_identifier.return_value = robot

        with pytest.raises(HTTPException) as exc_info:
            service.create_access_token_by_basic_credentials(_make_credentials())

        assert exc_info.value.status_code == 403

    def test_robot_rechazado_lanza_403(self, service, robot_service):
        robot = _make_robot(status=RobotStatus.REJECTED)
        robot_service.get_robot_by_external_identifier.return_value = robot

        with pytest.raises(HTTPException) as exc_info:
            service.create_access_token_by_basic_credentials(_make_credentials())

        assert exc_info.value.status_code == 403


class TestCreateAccessToken:
    def test_genera_token_con_datos_correctos(self, service, encryption_service):
        robot = _make_robot()

        service.create_access_token(robot)

        call_args = encryption_service.create_bearer_access_token.call_args
        data = call_args[1]["data"]
        assert data["sub"] == str(robot.id)
        assert data["role"] == "robot"
        assert "broker:report_log" in data["scope"]
        assert "broker:listen_commands" in data["scope"]
