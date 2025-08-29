from typing import Annotated

from fastapi import Depends
from sqlmodel import select

from .user import User
from ..encryption import EncryptionServiceDep, EncryptionService
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
        return self.db_session.exec(
            select(User)
                .where(User.usr_name == username)
                .where(User.usr_psw == psw)
        ).one()

    def get_user_by_token(self, token: str) -> User | None:
        username = self.encryption_service.decode_token(token).get("sub")

        user: User | None = self.db_session.exec(
            select(User).where(User.usr_name == username)
        ).one()

        return user

UserServiceDep = Annotated[UserService, Depends(UserService)]
