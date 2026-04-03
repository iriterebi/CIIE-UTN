from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import logging


class Config(BaseSettings):
    """
    Controlador de robot — se registra en la API y escucha comandos vía rosbridge.
    """

    model_config = SettingsConfigDict(  # pyright: ignore[reportUnannotatedClassAttribute]
        env_file='.env',
        env_file_encoding='utf-8',
        frozen=True,
        extra='ignore',
        cli_parse_args=True,
        cli_prog_name="robot-controller",
    )

    server_url: str = Field(
        validation_alias=AliasChoices('s', 'server_url')
    )

    rosbridge_url: str = Field(
        validation_alias=AliasChoices('r', 'rosbridge_url')
    )

    arduino_port: str = Field(
        validation_alias=AliasChoices('p', 'arduino_port'),
        description="puerto serial del arduino"
    )

    create_default_metadata: bool =  Field(
        default=False,
        validation_alias=AliasChoices('c', 'create_default_metadata'),
        description="crea el archivo de credenciales si no existe"
    )

    mock_robot: bool = Field(
        default=False,
        validation_alias=AliasChoices('mock', 'mock_robot')
    )

    metadata_file: str = Field(
        default='./robot-metadata.json',
        validation_alias=AliasChoices('m', 'metadata_file'),
        description="Ruta al archivo de credenciales del robot"
    )

    socket_path: str = Field(
        default='/tmp/robot-controller.sock',
        validation_alias=AliasChoices('socket_path'),
        description="Ruta del Unix socket para gestión (CLI)"
    )


config = Config() # pyright: ignore[reportCallIssue]


logging.debug(config)
