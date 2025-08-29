from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from .services.user import UserService, User, get_current_user


router = APIRouter(tags=["auth"])


@router.post('/login')
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_service: Annotated[UserService, Depends(UserService)],
):

    user = user_service.get_user_by_credentials(
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    token = user.create_access_token(user)

    return token


@router.get("/me", response_model=User)
def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    return current_user

