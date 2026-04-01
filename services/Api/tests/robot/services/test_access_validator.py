from unittest.mock import MagicMock
from uuid import uuid4
import pytest

from src.robot.services.access_validator import AccessValidator, UserRobotAccessSession
from src.robot.entities.errors import RobotAccessException
from src.robot.entities.json_rpc_commands import UserWsAuthentication


@pytest.fixture
def encryption_service():
    return MagicMock()


@pytest.fixture
def validator(encryption_service):
    return AccessValidator(encryption_service)


class TestGrantAccess:
    def test_acceso_concedido_con_datos_validos(self, validator, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "type": "robot_access",
            "robot_id": str(robot_id),
            "sub": "testuser",
        }
        session = UserRobotAccessSession("testuser")

        result = validator.grant_access("token", robot_id, session)

        assert result is True

    def test_tipo_incorrecto_deniega_acceso(self, validator, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "type": "other",
            "robot_id": str(robot_id),
            "sub": "testuser",
        }
        session = UserRobotAccessSession("testuser")

        assert validator.grant_access("token", robot_id, session) is False

    def test_robot_id_no_coincide_deniega_acceso(self, validator, encryption_service):
        encryption_service.decode_token.return_value = {
            "type": "robot_access",
            "robot_id": str(uuid4()),  # UUID diferente
            "sub": "testuser",
        }
        session = UserRobotAccessSession("testuser")

        assert validator.grant_access("token", uuid4(), session) is False

    def test_username_no_coincide_deniega_acceso(self, validator, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "type": "robot_access",
            "robot_id": str(robot_id),
            "sub": "otrouser",
        }
        session = UserRobotAccessSession("testuser")

        assert validator.grant_access("token", robot_id, session) is False

    def test_sin_session_no_valida_username(self, validator, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "type": "robot_access",
            "robot_id": str(robot_id),
            "sub": "cualquier_user",
        }

        result = validator.grant_access("token", robot_id, None)

        assert result is True

    def test_token_invalido_retorna_false(self, validator, encryption_service):
        encryption_service.decode_token.side_effect = Exception("invalid token")

        result = validator.grant_access("bad-token", uuid4(), None)

        assert result is False


class TestValidateGrantAccess:
    def test_acceso_valido_no_lanza_error(self, validator, encryption_service):
        robot_id = uuid4()
        encryption_service.decode_token.return_value = {
            "type": "robot_access",
            "robot_id": str(robot_id),
            "sub": "testuser",
        }
        session = UserRobotAccessSession("testuser")

        validator.validate_grant_access("token", robot_id, session)  # no exception

    def test_acceso_denegado_lanza_robot_access_exception(self, validator, encryption_service):
        encryption_service.decode_token.return_value = {"type": "other"}
        session = UserRobotAccessSession("testuser")

        with pytest.raises(RobotAccessException):
            validator.validate_grant_access("token", uuid4(), session)


class TestCreateRobotAccessSession:
    def test_crea_session_desde_token(self, validator, encryption_service):
        encryption_service.decode_token.return_value = {"sub": "testuser"}
        auth = UserWsAuthentication(token="valid-token")

        session = validator.create_robot_access_session(auth)

        assert session.username == "testuser"
        encryption_service.decode_token.assert_called_once_with("valid-token")
