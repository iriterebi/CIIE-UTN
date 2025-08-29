import jwt

from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

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

        expire = datetime.now(timezone.utc) + access_token_expires

        to_encode.update({
            "exp": expire
        })

        access_token =  jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)

        return AccessToken(access_token=access_token, token_type="bearer")

    def decode_token(self, token: str) -> dict:
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])


EncryptionServiceDep = Annotated[EncryptionService, Depends(EncryptionService)]
