from uuid import UUID
from ..auth.services.encryption import EncryptionServiceDep


class AccessValidator:
    def __init__(self, encryption_service: EncryptionServiceDep):
        self.encryption_service = encryption_service

    def grant_access(self, token: str, robot_id: UUID) -> bool:
        try:
            data = self.encryption_service.decode_token(token)

            return "robot_id" in data and isinstance(data["robot_id"], str) and UUID(data.get("robot_id")) == robot_id
        except:
            return False
