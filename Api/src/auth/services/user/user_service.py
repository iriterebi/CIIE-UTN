from typing import Annotated

from fastapi import Depends
from sqlmodel import select

from .user import User
from ..encryption import EncryptionServiceDep, EncryptionService, AccessToken
from ....db_connection import DbSessionDep


class UserService:
    encryption_service: EncryptionService

    def __init__(
        self,
        encryption_service: EncryptionServiceDep,
        db_session: DbSessionDep
    ):
        self.encryption_service = encryption_service
        self.db_session = db_session

    def get_user_by_credentials(self, username: str, psw: str) -> User | None:
        user = self.db_session.query(User).filter(User.usr_name == username).first()

        if not user:
            return None

        if not self.encryption_service.verify_pwd(psw, user.usr_psw):
            return None

        return user

    def get_user_by_token(self, token: str) -> User | None:
        username = self.encryption_service.decode_token(token).get("sub")

        user: User | None = self.db_session.exec(
            select(User).where(User.usr_name == username)
        ).one()

        return user

    def create_access_token(self, user: User) -> AccessToken:

        data = {
            "sub": user.usr_name,
            "role": user.statuss,
        }

        if user.is_admin:
            data["role"] = "admin"
        else:
            data["role"] = "user"

        return self.encryption_service.create_bearer_access_token(data=data)


UserServiceDep = Annotated[UserService, Depends(UserService)]
