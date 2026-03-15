from dataclasses import dataclass
from uuid import UUID
from warnings import deprecated

JSONRPC_PARSE_ERROR = -32700  # Parse error       Invalid JSON was received by the server. An error occurred on the server while parsing the JSON text.
JSONRPC_Invalid_Request = -32600  # Invalid Request   The JSON sent is not a valid Request object.
JSONRPC_Method_NOT_found = -32601  # Method not found  The method does not exist / is not available.
JSONRPC_INVALID_PARAMS = -32602  # Invalid params    Invalid method parameter(s).
JSONRPC_INTERNAL_ERROR = -32603  # Internal error    Internal JSON-RPC error.


# JSONRPC_-32000 to -32099 	Server error 	Reserved for implementation-defined server-errors.

def serialise_as_jsonrpc_error(error: Exception, message_id: str | int, code: int, message: str | None = None) -> dict:
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": code,
            "message": message if message is not None else type(error).__name__,
            "data": error.to_dict() if isinstance(error, SerializableException) else error,
        },
        "id": message_id
    }


class SerializableException(Exception):
    def to_dict(self) -> dict:
        raise NotImplementedError('SerializableException must be implemented.')

    @deprecated("prefer use of serialise_as_jsonrpc_error function instead")
    def to_jsonrpc(self, message_id: str | None = None) -> dict:
        return serialise_as_jsonrpc_error(self, message_id, JSONRPC_INTERNAL_ERROR)


@dataclass(frozen=True)
class RobotNotFoundException(SerializableException):
    robot_id: str | UUID

    def to_dict(self) -> dict:
        return {
            "robot_id": str(self.robot_id),
        }


@dataclass(frozen=True)
class RobotAccessException(SerializableException):
    robot_id: str | UUID

    def to_dict(self) -> dict:
        return {
            "robot_id": str(self.robot_id)
        }


class UserAccessException(SerializableException):
    def to_dict(self) -> dict:
        return {
            "description": "user sessions is not valid"
        }


class UserValidationTimeoutException(SerializableException):
    def to_dict(self) -> dict:
        return {
            "description": "user auth timeout"
        }


@dataclass(frozen=True)
class RobotNotApprovedException(SerializableException):
    robot_id: str | UUID
    current_status: str

    def to_dict(self) -> dict:
        return {
            "robot_id": str(self.robot_id),
            "current_status": self.current_status,
        }


@dataclass(frozen=True)
class InvalidRobotStatusException(SerializableException):
    robot_id: str | UUID
    current_status: str
    expected_status: str

    def to_dict(self) -> dict:
        return {
            "robot_id": str(self.robot_id),
            "current_status": self.current_status,
            "expected_status": self.expected_status,
        }
