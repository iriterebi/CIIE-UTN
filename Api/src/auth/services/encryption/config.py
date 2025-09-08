from typing import Annotated
from fastapi import Depends
from ....config import JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from dataclasses import dataclass


@dataclass
class EncryptionServiceConfiguration:
    secret_key: str = ""
    algorithm: str = "HS256"
    toket_expiration_time: int = 30


def get_env_encryption_conf():
    return EncryptionServiceConfiguration(
        secret_key=JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
        toket_expiration_time=ACCESS_TOKEN_EXPIRE_MINUTES
    )


EncryptionConfigDep = Annotated[EncryptionServiceConfiguration, Depends(
    get_env_encryption_conf)]
