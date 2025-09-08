from typing import Annotated
from datetime import datetime, timedelta, timezone
import jwt
import bcrypt
from fastapi import Depends

from .config import EncryptionConfigDep
from .access_token import AccessToken


class EncryptionService:
    secret_key: str
    algorithm: str
    toket_expiration_time: int

    def __init__(
        self,
        config: EncryptionConfigDep
    ) -> None:
        self.secret_key = config.secret_key
        self.algorithm = config.algorithm
        self.toket_expiration_time = config.toket_expiration_time

    def create_bearer_access_token(self, data: dict) -> AccessToken:
        access_token_expires = timedelta(minutes=self.toket_expiration_time)
        to_encode = data.copy()

        now = datetime.now(timezone.utc)
        expire = now + access_token_expires

        to_encode.update({
            "iat": now,
            "nbf": now,
            "exp": expire,
        })

        access_token = jwt.encode(
            to_encode, self.secret_key, algorithm=self.algorithm)

        return AccessToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=int(access_token_expires.total_seconds()),
            scope=to_encode.get("scope", "")
        )

    def decode_token(self, token: str) -> dict:
        data: dict = self.decode_token_without_verify(token)

        data.pop("iat")
        nbf = datetime.fromtimestamp(data.pop("nbf"))
        exp = datetime.fromtimestamp(data.pop("exp"))

        if not nbf <= datetime.now() <= exp:
            raise ValueError("Token is not valid")

        return data

    def decode_token_without_verify(self, token: str) -> dict:
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

    def encrypt_psw(self, plain_text_psw) -> str:
        return bcrypt.hashpw(
            plain_text_psw.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

    def verify_pwd(self, plain_text_psw, hashed_psw) -> bool:
        return bcrypt.checkpw(plain_text_psw.encode('utf-8'), hashed_psw.encode('utf-8'))


EncryptionServiceDep = Annotated[EncryptionService, Depends(EncryptionService)]
