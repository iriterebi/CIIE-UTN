from pydantic import BaseModel
from uuid import UUID as PythonUUID

class RobotCommand(BaseModel):
    robot_id: PythonUUID
    args: dict
    pass

class RobotResponse(BaseModel):
    pass
