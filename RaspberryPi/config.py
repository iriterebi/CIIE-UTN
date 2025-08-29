import os
from dotenv import load_dotenv


load_dotenv(".env.defaults", override=True)
load_dotenv(".env", override=True)


def _get_required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set.")
    return value



# Environment variables
SERVER_URL: str = _get_required_env('SERVER_URL')
ARDUINO_PORT: str = _get_required_env('ARDUINO_PORT')
