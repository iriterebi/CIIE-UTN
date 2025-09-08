from pydantic import BaseModel

class RobotCommand(BaseModel):
    robot_id: str
    args: dict
    pass

class RobotResponse(BaseModel):
    pass
