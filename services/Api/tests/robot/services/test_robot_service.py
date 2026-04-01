from unittest.mock import MagicMock
from uuid import uuid4, UUID
import pytest

from src.robot.services.robot_service import RobotService, get_current_robot
from src.robot.entities.robot import Robot, RobotInput, RobotStatus, RobotRegistrationInput, RobotApprovalInput
from src.robot.entities.errors import RobotNotFoundException, InvalidRobotStatusException
from fastapi import HTTPException
from jwt import InvalidTokenError


@pytest.fixture
def repository():
    return MagicMock()


@pytest.fixture
def encryption_service():
    mock = MagicMock()
    mock.encrypt_psw.return_value = "hashed_password"
    mock.decode_token.return_value = {"sub": str(uuid4()), "role": "robot"}
    return mock


@pytest.fixture
def service(repository, encryption_service):
    return RobotService(repository, encryption_service)


def _make_robot(
    robot_id=None,
    external_identifier=None,
    status=RobotStatus.PENDING_APPROVAL,
    name=None,
    psw="hashed",
):
    robot = MagicMock(spec=Robot)
    robot.id = robot_id or uuid4()
    robot.external_identifier = external_identifier or str(uuid4())
    robot.status = status
    robot.name = name
    robot.psw = psw
    return robot


class TestListRobots:
    def test_delega_al_repositorio(self, service, repository):
        robots = [_make_robot(), _make_robot()]
        repository.list.return_value = robots

        result = service.list_robots()

        assert result == robots
        repository.list.assert_called_once()


class TestGetRobotById:
    def test_robot_encontrado(self, service, repository):
        robot = _make_robot()
        repository.get_by_id.return_value = robot

        result = service.get_robot_by_id(robot.id)

        assert result == robot

    def test_robot_no_encontrado(self, service, repository):
        repository.get_by_id.return_value = None

        result = service.get_robot_by_id(uuid4())

        assert result is None


class TestExists:
    def test_robot_existe(self, service, repository):
        repository.get_by_id.return_value = _make_robot()
        assert service.exists(uuid4()) is True

    def test_robot_no_existe(self, service, repository):
        repository.get_by_id.return_value = None
        assert service.exists(uuid4()) is False


class TestValidateExistsRobot:
    def test_robot_existe_no_lanza_error(self, service, repository):
        repository.get_by_id.return_value = _make_robot()
        service.validate_exists_robot(uuid4())  # no exception

    def test_robot_no_existe_lanza_error(self, service, repository):
        repository.get_by_id.return_value = None

        with pytest.raises(RobotNotFoundException):
            service.validate_exists_robot(uuid4())

    def test_uuid_invalido_lanza_robot_not_found(self, service, repository):
        repository.get_by_id.side_effect = ValueError("bad uuid")

        with pytest.raises(RobotNotFoundException):
            service.validate_exists_robot("no-es-uuid")


class TestRegisterRobot:
    def test_robot_nuevo_se_crea(self, service, repository, encryption_service):
        repository.get_by_external_identifier.return_value = None
        new_robot = _make_robot(status=RobotStatus.PENDING_APPROVAL)
        repository.save.return_value = new_robot

        ext_id = uuid4()
        registration = RobotRegistrationInput(
            external_identifier=ext_id,
            psw="plain_password",
        )

        result = service.register_robot(registration)

        assert result == new_robot
        encryption_service.encrypt_psw.assert_called_once_with("plain_password")
        repository.save.assert_called_once()

    def test_robot_existente_retorna_sin_crear(self, service, repository, encryption_service):
        existing = _make_robot()
        repository.get_by_external_identifier.return_value = existing

        registration = RobotRegistrationInput(
            external_identifier=uuid4(),
            psw="password",
        )

        result = service.register_robot(registration)

        assert result == existing
        encryption_service.encrypt_psw.assert_not_called()
        repository.save.assert_not_called()


class TestApproveRobot:
    def test_aprobacion_exitosa(self, service, repository):
        robot = _make_robot(status=RobotStatus.PENDING_APPROVAL)
        repository.get_by_id.return_value = robot
        repository.save.return_value = robot

        approval = RobotApprovalInput(name="Robot Lab 1", description="Brazo 7DOF")

        result = service.approve_robot(robot.id, approval)

        assert result.name == "Robot Lab 1"
        assert result.description == "Brazo 7DOF"
        assert result.status == RobotStatus.APPROVED
        repository.save.assert_called_once()

    def test_robot_no_encontrado(self, service, repository):
        repository.get_by_id.return_value = None

        with pytest.raises(RobotNotFoundException):
            service.approve_robot(uuid4(), RobotApprovalInput(name="Test"))

    def test_estado_incorrecto(self, service, repository):
        robot = _make_robot(status=RobotStatus.APPROVED)
        repository.get_by_id.return_value = robot

        with pytest.raises(InvalidRobotStatusException):
            service.approve_robot(robot.id, RobotApprovalInput(name="Test"))


class TestRejectRobot:
    def test_rechazo_exitoso(self, service, repository):
        robot = _make_robot(status=RobotStatus.PENDING_APPROVAL)
        repository.get_by_id.return_value = robot
        repository.save.return_value = robot

        result = service.reject_robot(robot.id)

        assert result.status == RobotStatus.REJECTED
        repository.save.assert_called_once()

    def test_robot_no_encontrado(self, service, repository):
        repository.get_by_id.return_value = None

        with pytest.raises(RobotNotFoundException):
            service.reject_robot(uuid4())

    def test_estado_incorrecto(self, service, repository):
        robot = _make_robot(status=RobotStatus.APPROVED)
        repository.get_by_id.return_value = robot

        with pytest.raises(InvalidRobotStatusException):
            service.reject_robot(robot.id)


class TestGetRobotByToken:
    def test_token_valido_con_role_robot(self, service, repository, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "sub": str(robot_id),
            "role": "robot",
        }
        robot = _make_robot(robot_id=robot_id)
        repository.get_by_id.return_value = robot

        result = service.get_robot_by_token("valid-token")

        assert result == robot

    def test_role_no_robot_retorna_none(self, service, encryption_service):
        encryption_service.decode_token.return_value = {
            "sub": "someuser",
            "role": "user",
        }

        result = service.get_robot_by_token("user-token")

        assert result is None

    def test_sin_sub_retorna_none(self, service, encryption_service):
        encryption_service.decode_token.return_value = {"role": "robot"}

        result = service.get_robot_by_token("no-sub-token")

        assert result is None


class TestGetCurrentRobot:
    def test_robot_encontrado(self):
        robot = _make_robot()
        robot_service = MagicMock()
        robot_service.get_robot_by_token.return_value = robot

        result = get_current_robot(robot_service, "valid-token")

        assert result == robot

    def test_robot_no_encontrado_lanza_401(self):
        robot_service = MagicMock()
        robot_service.get_robot_by_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_robot(robot_service, "bad-token")

        assert exc_info.value.status_code == 401

    def test_token_invalido_lanza_401(self):
        robot_service = MagicMock()
        robot_service.get_robot_by_token.side_effect = InvalidTokenError()

        with pytest.raises(HTTPException) as exc_info:
            get_current_robot(robot_service, "invalid-token")

        assert exc_info.value.status_code == 401
