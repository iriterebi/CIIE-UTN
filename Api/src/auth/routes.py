from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.security import OAuth2PasswordRequestForm

from .services.encryption import EncryptionServiceDep
from .services.user import UserService, User, get_current_user, UserBase

router = APIRouter(tags=["auth"])


@router.post('/login')
def login(
        form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
        user_service: Annotated[UserService, Depends(UserService)],
):
    """ OAuth 2.0 compatible token login, get an access token for future requests """
    user = user_service.get_user_by_credentials(
        form_data.username,
        form_data.password
    )

    if not user:
        raise HTTPException(
            status_code=400, detail="Incorrect username or password")

    token = user_service.create_access_token(user)

    return token


@router.post("/signup")
def signup(
        user_data: UserBase,
        user_service: Annotated[UserService, Depends(UserService)],
):
    user = user_service.register_new_user(user_data)

    token = user_service.create_access_token(user)

    return {'user': user, 'token': token}


@router.get("/me", response_model=User)
def read_users_me(
        current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    return current_user


@router.post("/request_robot_access")
def request_robot_access(
        encryption_service: EncryptionServiceDep,
        current_user: Annotated[User, Depends(get_current_user)],
        robot_id: Annotated[str, Body(embed=True)],
):
    # TODO: validate existence and diponibility

    return encryption_service.create_bearer_access_token({
        'user_id': current_user.id,
        'robot_id': robot_id,
    })
