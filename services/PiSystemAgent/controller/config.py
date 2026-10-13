import logging

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """
    Controlador de robot — se registra en la API y escucha comandos vía WS directo a la API.
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

    local_strategy: str = Field(
        default='MockStrategy',
        validation_alias=AliasChoices('local_strategy'),
        description="Strategy local a usar al arrancar"
    )

    remote_strategy: str = Field(
        default='WsStrategy',
        validation_alias=AliasChoices('remote_strategy'),
        description="Strategy remoto a usar al arrancar"
    )

    ros2_node_name: str = Field(
        default='labs_remoto_robot',
        validation_alias=AliasChoices('ros2_node_name'),
        description="Nombre del nodo rclpy (Ros2Strategy)"
    )

    ros2_command_topic: str = Field(
        default='/inorbit/custom_command',
        validation_alias=AliasChoices('ros2_command_topic'),
        description="Topic ROS 2 donde se publican los comandos (Ros2Strategy)"
    )

    ros2_data_topic: str = Field(
        default='/inorbit/custom_data',
        validation_alias=AliasChoices('ros2_data_topic'),
        description="Topic ROS 2 de telemetría Key=Value que se suscribe (Ros2Strategy)"
    )

    ros2_domain_id: int = Field(
        default=42,
        validation_alias=AliasChoices('ros2_domain_id'),
        description="ROS_DOMAIN_ID DDS (Ros2Strategy); debe coincidir con el agente ROS de la Pi"
    )

    camera_node_name: str = Field(
        default='labs_remoto_camera',
        validation_alias=AliasChoices('camera_node_name'),
        description="Nombre del nodo rclpy para la cámara (CameraRelay), distinto del nodo del brazo"
    )

    camera_topic: str = Field(
        default='usb_cam/image_raw',
        validation_alias=AliasChoices('camera_topic'),
        description="Topic ROS 2 de video (sensor_msgs/Image, bgr8) que suscribe CameraRelay"
    )

    camera_jpeg_quality: int = Field(
        default=80,
        validation_alias=AliasChoices('camera_jpeg_quality'),
        description="Calidad JPEG (0-100) usada para codificar cada frame antes de enviarlo"
    )


config = Config() # pyright: ignore[reportCallIssue]


logging.debug(config)
