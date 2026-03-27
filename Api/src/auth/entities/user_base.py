from typing import Annotated
from pydantic import BaseModel, Field, EmailStr

class UserBase(BaseModel):
    nombre: Annotated[str, Field()]
    email: EmailStr
    usr_name: Annotated[str, Field()]
    usr_psw: Annotated[str, Field(min_length=6)]
    usr_pronouns: Annotated[str, Field()]
