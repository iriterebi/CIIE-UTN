from pydantic import BaseModel
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

TokenStrDep = Annotated[str, Depends(oauth2_scheme)]

class AccessToken(BaseModel):
    access_token: str
    token_type: str
