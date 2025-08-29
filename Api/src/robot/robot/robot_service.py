from typing import List, Annotated
from fastapi import Depends

from src.db_connection import DbSessionDep
from src.auth.services.user import User

from .robot import Robot


class RobotService:
    def __init__(
        self,
        db_session: DbSessionDep
    ):
        self.db_session = db_session


    def list_robots(self, user: User | None) -> List[Robot]:
        return self.db_session.query(Robot).all()

    def get_robot_by_id(self, id: int) -> Robot | None:
        return self.db_session.query(Robot).filter(Robot.id == id).first()





RobotServiceDep = Annotated[RobotService, Depends(RobotService)]
