from uuid import UUID

from pydantic import BaseModel

class RRobotCommand(BaseModel):
    method: str


class RobotResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: dict | None = None
    error: dict | None = None
    id: str | int | None = None
    method: str | None = None
    params: dict | None = None

class UserWsAuthentication(BaseModel):
    token: str
    robot_id: UUID
