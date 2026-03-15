from typing import Annotated
from fastapi import Depends
from uuid import UUID as PythonUUID
from contextlib import contextmanager
from ..entities import Robot, RobotStatus
from ...db_connection import DbSessionDep



class RobotRepository:
    db_session: DbSessionDep

    def __init__(
            self,
            db_session: DbSessionDep,
    ):
        self.db_session = db_session

    def list(self) -> list[Robot]:
        return self.db_session.query(Robot).all()

    def get_by_id(self, robot_id: str) -> Robot | None:
        if not isinstance(robot_id, PythonUUID):
            robot_id = PythonUUID(robot_id)

        return self.db_session.query(Robot).filter(Robot.id == robot_id).first()

    def get_by_external_identifier(self, external_identifier: str) -> Robot | None:
        return self.db_session.query(Robot).filter(Robot.external_identifier == external_identifier).first()

    def list_by_status(self, status: RobotStatus) -> list[Robot]:
        return self.db_session.query(Robot).filter(Robot.status == status).all()

    def save(self, robot: Robot) -> Robot:
        self.db_session.add(robot)
        self.db_session.commit()
        self.db_session.refresh(robot)
        return robot

    @contextmanager
    def transaction(self, nested: bool = False):
        tx = self.db_session.begin(nested=nested)
        try:
            yield tx
            tx.commit()
        except Exception:
            tx.rollback()
            raise


def get_robot_repository(
        db_session: DbSessionDep,
) -> RobotRepository:
    return RobotRepository(db_session)

RobotRepositoryDep = Annotated[RobotRepository, Depends(get_robot_repository)]
