from unittest.mock import MagicMock, patch, PropertyMock
import pytest
from fastapi import HTTPException
from jwt import ExpiredSignatureError

from src.auth.services.user_service import UserService
from src.auth.entities.user import User
from src.auth.entities.user_base import UserBase
from src.auth.entities.access_token import AccessToken


@pytest.fixture
def encryption_service():
    mock = MagicMock()
    mock.verify_pwd.return_value = True
    mock.encrypt_psw.return_value = "hashed_password"
    mock.decode_token.return_value = {"sub": "testuser"}
    mock.create_bearer_access_token.return_value = AccessToken(
        access_token="token123",
        token_type="bearer",
        scope="",
        expires_in=1800,
    )
    return mock


@pytest.fixture
def db_session():
    return MagicMock()


@pytest.fixture
def service(encryption_service, db_session):
    return UserService(encryption_service, db_session)


def _make_user(usr_name="testuser", statuss="alumno", usr_psw="hashed"):
    user = MagicMock(spec=User)
    user.usr_name = usr_name
    user.usr_psw = usr_psw
    user.statuss = statuss
    user.is_admin = statuss == "profe"
    return user


class TestGetUserByCredentials:
    def test_usuario_encontrado_y_password_correcto(self, service, db_session, encryption_service):
        user = _make_user()
        db_session.query.return_value.filter.return_value.first.return_value = user

        result = service.get_user_by_credentials("testuser", "password123")

        assert result == user
        encryption_service.verify_pwd.assert_called_once_with("password123", "hashed")

    def test_usuario_no_encontrado(self, service, db_session):
        db_session.query.return_value.filter.return_value.first.return_value = None

        result = service.get_user_by_credentials("noexiste", "password")

        assert result is None

    def test_password_incorrecto(self, service, db_session, encryption_service):
        user = _make_user()
        db_session.query.return_value.filter.return_value.first.return_value = user
        encryption_service.verify_pwd.return_value = False

        result = service.get_user_by_credentials("testuser", "wrong")

        assert result is None


class TestGetUserByToken:
    def test_token_valido(self, service, db_session, encryption_service):
        user = _make_user()
        db_session.exec.return_value.one.return_value = user

        result = service.get_user_by_token("valid-token")

        assert result == user
        encryption_service.decode_token.assert_called_once_with("valid-token")

    def test_token_expirado_retorna_none(self, service, encryption_service):
        encryption_service.decode_token.side_effect = ExpiredSignatureError()

        result = service.get_user_by_token("expired-token")

        assert result is None


class TestCreateAccessToken:
    def test_usuario_admin(self, service, encryption_service):
        user = _make_user(statuss="profe")

        service.create_access_token(user)

        call_args = encryption_service.create_bearer_access_token.call_args
        data = call_args[1]["data"]
        assert data["role"] == "admin"
        assert data["sub"] == "testuser"

    def test_usuario_regular(self, service, encryption_service):
        user = _make_user(statuss="alumno")

        service.create_access_token(user)

        call_args = encryption_service.create_bearer_access_token.call_args
        data = call_args[1]["data"]
        assert data["role"] == "user"


class TestRegisterNewUser:
    def test_registro_exitoso(self, service, db_session, encryption_service):
        db_session.query.return_value.filter.return_value.count.return_value = 0

        user_base = MagicMock(spec=UserBase)
        user_base.nombre = "Test User"
        user_base.email = "test@test.com"
        user_base.usr_name = "testuser"
        user_base.usr_psw = "password123"
        user_base.usr_pronouns = "él"

        result = service.register_new_user(user_base)

        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        db_session.refresh.assert_called_once()

        created_user = db_session.add.call_args[0][0]
        assert created_user.nombrecompleto == "Test User"
        assert created_user.statuss == "alumno"
        assert created_user.usr_psw == "hashed_password"
        encryption_service.encrypt_psw.assert_called_once_with("password123")

    def test_usuario_duplicado_lanza_error(self, service, db_session):
        db_session.query.return_value.filter.return_value.count.return_value = 1

        user_base = MagicMock(spec=UserBase)
        user_base.usr_name = "duplicado"

        with pytest.raises(HTTPException) as exc_info:
            service.register_new_user(user_base)

        assert exc_info.value.status_code == 400
