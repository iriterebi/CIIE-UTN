import logging
from datetime import datetime
from uuid import UUID

from ..entities.errors import RobotAccessException
from ..entities.json_rpc_commands import UserWsAuthentication
from ...auth.services import EncryptionServiceDep


#
# # Create a logger instance
# logger = logging.getLogger(__name__)
# logger.setLevel(logging.NOTSET)  # Set the desired logging level
#
# # Create a console handler and formatter
# handler = logging.StreamHandler()
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
# logger.addHandler(handler)


class UserRobotAccessSession:
    username: str
    expiration_time: datetime

    def __init__(self, username: str):
        self.username = username


class AccessValidator:
    def __init__(self, encryption_service: EncryptionServiceDep):
        self.encryption_service = encryption_service

    def grant_access(self, token: str, robot_id: UUID, user_session: UserRobotAccessSession | None) -> bool:
        try:
            print(f"Decoding token: {token}")
            print(f"robot_id: {robot_id}")
            print(f"user_session", user_session)

            data = self.encryption_service.decode_token(token)

            print(f"data {data}")

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
        except Exception as e:
            print(f"Error decoding token: {token}")
            return False

    def validate_grant_access(self, token: str, robot_id: UUID, user_session: UserRobotAccessSession) -> None:
        print("Validating grant access token")
        if not self.grant_access(token, robot_id, user_session):
            raise RobotAccessException(robot_id)

    def create_robot_access_session(self, user_auth: UserWsAuthentication) -> UserRobotAccessSession:
        token = user_auth.token

        username = self.encryption_service.decode_token(token).get("sub")

        return UserRobotAccessSession(username)
