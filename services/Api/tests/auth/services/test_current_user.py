from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from src.auth.services.current_user import get_current_user
from src.auth.entities.user import User


class TestGetCurrentUser:
    def test_usuario_valido(self):
        user = MagicMock(spec=User)
        user_service = MagicMock()
        user_service.get_user_by_token.return_value = user

        result = get_current_user(user_service, "valid-token")

        assert result == user
        user_service.get_user_by_token.assert_called_once_with("valid-token")

    def test_usuario_no_encontrado_lanza_401(self):
        user_service = MagicMock()
        user_service.get_user_by_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(user_service, "bad-token")

        assert exc_info.value.status_code == 401
