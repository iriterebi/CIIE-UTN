from fastapi import HTTPException

from .user import User
from .user_service import UserServiceDep
from ..encryption import TokenStrDep


def get_current_user(
    user_service: UserServiceDep,
    token: TokenStrDep
) -> User:

    user = user_service.get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
