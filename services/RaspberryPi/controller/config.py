from pydantic_settings import BaseSettings, SettingsConfigDict
import logging


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        frozen=True,
        extra='ignore',
    )

    server_url: str
    rosbridge_url: str
    arduino_port: str
    create_default_metadata: bool
    mock_robot: bool
    metadata_file: str = './robot-metadata.json'


config = Config()  # type: ignore[call-arg]


logging.debug(config)
