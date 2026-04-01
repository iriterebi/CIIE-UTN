from fastapi import HTTPException

from ..entities import User, TokenStrDep
from .user_service import UserServiceDep


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
