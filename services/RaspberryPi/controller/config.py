from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(frozen=True)

    server_url: str
    rosbridge_url: str
    arduino_port: str
    create_default_metadata: bool
    mock_robot: bool
    metadata_file: str = './robot-metadata.json'


config = Config()  # type: ignore[call-arg]
