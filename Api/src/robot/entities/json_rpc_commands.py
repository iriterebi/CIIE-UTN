from uuid import UUID

from pydantic import BaseModel

class RRobotCommand(BaseModel):
    method: str

class RobotCommand(BaseModel):
    robot_id: UUID
    args: RRobotCommand

class RobotCommandExtended(RRobotCommand):
    access_token: str
    robot_id: UUID


class RobotResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: dict | None = None
    error: dict | None = None
    id: str | int | None = None

class UserWsAuthentication(BaseModel):
    token: str
