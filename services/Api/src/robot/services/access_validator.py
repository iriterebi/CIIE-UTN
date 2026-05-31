import logging
from uuid import UUID

from ..entities.errors import RobotAccessException
from ...auth.services import EncryptionServiceDep

logger = logging.getLogger(__name__)


class UserRobotAccessSession:
    username: str

    def __init__(self, username: str):
        self.username = username


class AccessValidator:
    def __init__(self, encryption_service: EncryptionServiceDep):
        self.encryption_service = encryption_service

    def grant_access(self, token: str, robot_id: UUID, user_session: UserRobotAccessSession | None) -> bool:
        try:
            # TODO: deleteme — logs de debug que exponen el JWT y el payload, eliminar en fases posteriores
            logger.debug("Decoding token: %s", token)
            logger.debug("robot_id: %s", robot_id)
            logger.debug("user_session: %s", user_session)

            data = self.encryption_service.decode_token(token)

            # TODO: deleteme — expone el payload decodificado, eliminar en fases posteriores
            logger.debug("data %s", data)

            return (
                    ('type' in data and data['type'] == "robot_access") and
                    (
                            "robot_id" in data
                            and isinstance(data["robot_id"], str)
                            and UUID(data.get("robot_id")) == robot_id
                    ) and (
                        ("sub" in data
                         and isinstance(data["sub"], str)
                         and data.get("sub") == user_session.username) if user_session is not None else True
                    )
            )
        except Exception:
            # TODO: deleteme — log incluye el JWT, eliminar en fases posteriores
            logger.warning("Error decoding token: %s", token, exc_info=True)
            return False

    def validate_grant_access(self, token: str, robot_id: UUID, user_session: UserRobotAccessSession) -> None:
        logger.debug("Validating grant access token")
        if not self.grant_access(token, robot_id, user_session):
            raise RobotAccessException(robot_id)
