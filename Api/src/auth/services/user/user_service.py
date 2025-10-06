from typing import Annotated

from fastapi import Depends, HTTPException
from sqlmodel import select

from .user import User
from .user_base import UserBase
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

    def register_new_user(self, user_base: UserBase) -> User:
        if self.db_session.query(User).filter(User.usr_name == user_base.usr_name).count() > 0:
            raise HTTPException(status_code=400, detail=f"User already exist")

        user = User()
        user.nombrecompleto = user_base.nombre
        user.email = user_base.email
        user.usr_pronouns = user_base.usr_pronouns
        user.usr_name = user_base.usr_name
        user.statuss = 'alumno'
        user.usr_psw = self.encryption_service.encrypt_psw(user_base.usr_psw)

        self.db_session.add(user)
        self.db_session.commit()
        self.db_session.refresh(user)
        return user


UserServiceDep = Annotated[UserService, Depends(UserService)]
