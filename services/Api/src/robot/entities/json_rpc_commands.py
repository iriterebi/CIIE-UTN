from pydantic import BaseModel

class RRobotCommand(BaseModel):
    method: str


class RobotResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: dict | None = None
    error: dict | None = None
    id: str | int | None = None

class UserWsAuthentication(BaseModel):
    token: str
    robot_id: str
