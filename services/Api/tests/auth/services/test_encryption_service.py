from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest
import jwt

from src.auth.services.encryption_service import EncryptionService
from src.auth.entities.config import EncryptionServiceConfiguration
from src.auth.entities.access_token import AccessToken


@pytest.fixture
def config():
    return EncryptionServiceConfiguration(
        secret_key="test-secret-key-12345",
        algorithm="HS256",
        token_expiration_time=30,
    )


@pytest.fixture
def service(config):
    return EncryptionService(config)


class TestCreateBearerAccessToken:
    def test_retorna_access_token(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        assert isinstance(token, AccessToken)

    def test_token_type_es_bearer(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        assert token.token_type == "bearer"

    def test_expires_in_en_segundos(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        assert token.expires_in == 30 * 60  # 30 minutos en segundos

    def test_scope_vacio_por_defecto(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        assert token.scope == ""

    def test_scope_se_preserva(self, service):
        token = service.create_bearer_access_token({
            "sub": "testuser",
            "scope": "read write",
        })
        assert token.scope == "read write"

    def test_token_es_jwt_decodificable(self, service, config):
        token = service.create_bearer_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token.access_token,
            config.secret_key,
            algorithms=[config.algorithm],
        )
        assert payload["sub"] == "testuser"

    def test_token_contiene_claims_temporales(self, service, config):
        token = service.create_bearer_access_token({"sub": "testuser"})
        payload = jwt.decode(
            token.access_token,
            config.secret_key,
            algorithms=[config.algorithm],
        )
        assert "iat" in payload
        assert "nbf" in payload
        assert "exp" in payload

    def test_data_original_no_se_muta(self, service):
        data = {"sub": "testuser"}
        original = data.copy()
        service.create_bearer_access_token(data)
        assert data == original


class TestDecodeToken:
    def test_decodifica_token_valido(self, service):
        token = service.create_bearer_access_token({"sub": "testuser", "role": "admin"})
        data = service.decode_token(token.access_token)
        assert data["sub"] == "testuser"
        assert data["role"] == "admin"

    def test_remueve_claims_temporales(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        data = service.decode_token(token.access_token)
        assert "iat" not in data
        assert "nbf" not in data
        assert "exp" not in data

    def test_token_con_secret_incorrecto_falla(self, service, config):
        other_config = EncryptionServiceConfiguration(
            secret_key="otro-secret",
            algorithm="HS256",
            token_expiration_time=30,
        )
        other_service = EncryptionService(other_config)
        token = other_service.create_bearer_access_token({"sub": "testuser"})

        with pytest.raises(Exception):
            service.decode_token(token.access_token)

    def test_token_expirado_falla(self, config):
        # Crear token ya expirado manualmente
        expired_config = EncryptionServiceConfiguration(
            secret_key=config.secret_key,
            algorithm=config.algorithm,
            token_expiration_time=-1,  # negativo → ya expirado
        )
        expired_service = EncryptionService(expired_config)
        token = expired_service.create_bearer_access_token({"sub": "testuser"})

        with pytest.raises(Exception):
            expired_service.decode_token(token.access_token)


class TestDecodeTokenWithoutVerify:
    def test_decodifica_token(self, service):
        token = service.create_bearer_access_token({"sub": "testuser"})
        data = service.decode_token_without_verify(token.access_token)
        assert data["sub"] == "testuser"
        assert "iat" in data
        assert "nbf" in data
        assert "exp" in data


class TestEncryptPsw:
    def test_retorna_string(self, service):
        result = service.encrypt_psw("mi-password")
        assert isinstance(result, str)

    def test_hash_distinto_al_original(self, service):
        result = service.encrypt_psw("mi-password")
        assert result != "mi-password"

    def test_hashes_distintos_por_salt(self, service):
        hash1 = service.encrypt_psw("mi-password")
        hash2 = service.encrypt_psw("mi-password")
        assert hash1 != hash2


class TestVerifyPwd:
    def test_password_correcto(self, service):
        hashed = service.encrypt_psw("mi-password")
        assert service.verify_pwd("mi-password", hashed) is True

    def test_password_incorrecto(self, service):
        hashed = service.encrypt_psw("mi-password")
        assert service.verify_pwd("otro-password", hashed) is False
