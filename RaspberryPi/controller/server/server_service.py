"""
TODO
"""

from typing import List
import secrets
import string
import json
import logging
import time
import uuid
from datetime import datetime
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth
from ..config import SERVER_URL


class ServerServices:
    base_url: str
    robot_id: str
    robot_psw: str
    server_session: requests.Session | None = None
    expiration: int | None = None

    def __init__(self, base_url: str = SERVER_URL):
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)

    def load_external_config(self) -> bool:
        """ TODO """

        try:
            with open('./robot-metadata.json', 'r', encoding="utf-8") as robot_metadata:
                data = json.load(robot_metadata)
                self._load_config(data)
        except IOError as e:
            self.logger.error("Could not read robot-metadata.json: %s", e)
            return False

        return True

    def create_default_config(self) -> None:
        """ TODO """
        with open('./robot-metadata.json', 'w', encoding="utf-8") as robot_metadata:
            data: dict = {
                "robot_id": str(uuid.uuid4()),
                "robot_psw": self._create_strong_random_psw(),
                "creation_time": int(datetime.utcnow().timestamp())
            }
            json.dump(data, robot_metadata, indent=4)
            self._load_config(data)

    def _load_config(self, config: dict) -> None:
        self.robot_id = config.get("robot_id")
        self.robot_psw = config.get("robot_psw")

        assert self.robot_id is not None, "robot_id not found in config"
        assert self.robot_psw is not None, "robot_psw not found in config"

    def register(self) -> bool:
        """Registra el robot en el servidor (idempotente)."""
        try:
            response = requests.post(
                urljoin(self.base_url, "register"),
                json={
                    "external_identifier": self.robot_id,
                    "psw": self.robot_psw,
                },
                timeout=10,
            )

            if response.status_code == 200:
                body = response.json()
                self.logger.info(
                    "Registro exitoso. Estado: %s", body.get("status"))
                return True

            self.logger.error(
                "Registro fallido. Status: %s, Body: %s",
                response.status_code, response.text)
            return False
        except requests.exceptions.RequestException as e:
            self.logger.error("Error en registro: %s", e)
            return False

    def connect(self) -> int:
        """Intenta handshake con el servidor. Retorna el status code HTTP."""

        try:
            response = requests.post(
                urljoin(self.base_url, "handshake"),
                timeout=10,
                auth=HTTPBasicAuth(self.robot_id, self.robot_psw),
            )
        except requests.exceptions.RequestException as e:
            self.logger.error("Error de conexion en handshake: %s", e)
            return 0

        if response.status_code != 200:
            self.logger.error(
                "Handshake fallido. Status: %s, Body: %s",
                response.status_code, response.text)
            return response.status_code

        body: dict = response.json()
        self.expiration = body.get("expires_in")

        self.server_session = requests.Session()
        self.server_session.headers.update({
            "Authorization": f"{body.get('token_type')} {body.get('access_token')}"
        })

        self.logger.info(
            "Conexion exitosa con el servidor.")
        return 200

    def connect_with_retry(self, base_delay: int = 5, max_delay: int = 300) -> bool:
        """Registra el robot y reintenta handshake hasta ser aprobado."""
        self.register()

        attempt = 0
        while True:
            status_code = self.connect()

            if status_code == 200:
                return True

            if status_code == 403:
                delay = min(base_delay * (2 ** attempt), max_delay)
                self.logger.info(
                    "Robot pendiente de aprobacion. Reintentando en %ds...",
                    delay)
                time.sleep(delay)
                attempt += 1
            else:
                delay = min(base_delay * (2 ** attempt), max_delay)
                self.logger.warning(
                    "Error inesperado (status %s). Reintentando en %ds...",
                    status_code, delay)
                time.sleep(delay)
                attempt += 1

    def disconnect(self) -> None:
        """
        TODO
        """

        if self.server_session:
            self.server_session.close()
            self.server_session = None
            self.logger.info("Server session closed.")

    def __enter__(self):
        if not self.connect_with_retry():
            self.logger.critical(
                "No se pudo establecer conexion con el servidor.")
            raise EnvironmentError(
                "No se pudo establecer conexion con el servidor.")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.disconnect()

    def get_commands(self, on_command: callable = None) -> None:
        """
        TODO
        """

        try:
            response = self.server_session.get(
                urljoin(self.base_url, "get_data.php"), timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            data = response.text.strip().split('\n')

            on_command(data)

        except requests.exceptions.RequestException as e:
            self.logger.error("Error fetching commands from server: %s", e)
            return []

    def _create_strong_random_psw(self, longitud=24) -> str:
        caracteres = string.ascii_letters + string.digits + string.punctuation

        # Genera la contraseña asegurando que los caracteres sean elegidos de forma segura
        return ''.join(secrets.choice(caracteres) for i in range(longitud))
