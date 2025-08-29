import os
from dotenv import load_dotenv


load_dotenv()


def _get_required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set.")
    return value


# Environment variables
POSTGRES_PASSWORD: str = _get_required_env('POSTGRES_PASSWORD')
POSTGRES_USER: str = _get_required_env('POSTGRES_USER')
POSTGRES_DB: str = _get_required_env('POSTGRES_DB')
POSTGRES_URL: str = _get_required_env('POSTGRES_URL')


JWT_SECRET_KEY = _get_required_env("JWT_SECRET_KEY")
JWT_ALGORITHM = _get_required_env("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(_get_required_env("ACCESS_TOKEN_EXPIRE_MINUTES"))
