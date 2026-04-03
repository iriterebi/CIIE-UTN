from typing import Annotated
from fastapi import Depends
import functools

from ..entities import Robot
from ...auth.entities import User
from .stream_entities import (
    StreamSource as StreamSource,
    RobotConnection,
    UserConnection,
    UsersXRobotMapType,
)


class RobotInUseError(Exception):
    connection: UsersXRobotMapType

    def __init__(self, connection: UsersXRobotMapType):
        super().__init__("Robot already in use")
        self.connection = connection


class RobotConnectionRepository:
    def __init__(self):
        self._robots: dict[str, RobotConnection] = {}
        self._users: dict[str, UserConnection] = {}
        self._users_x_robot: list[UsersXRobotMapType] = []

    def addRobotConnection(self, robot: Robot, streamSource: StreamSource) -> RobotConnection:
        if str(robot.id) in self._robots:
            raise ValueError("Robot already connected")

        self._robots[str(robot.id)] = RobotConnection(streamSource, robot)
        return self._robots[str(robot.id)]

    def addUserConnection(self, user: User, streamSource: StreamSource) -> UserConnection:
        if str(user.id) in self._users:
            raise ValueError("User already connected")

        self._users[str(user.id)] = UserConnection(streamSource, user)
        return self._users[str(user.id)]

    def getRobotConnection(self, robot: Robot | str) -> RobotConnection | None:
        if isinstance(robot, Robot):
            robot = str(robot.id)

        return self._robots.get(robot)

    def getUserConnection(self, user: User | str) -> UserConnection | None:
        if isinstance(user, User):
            user = str(user.id)

        return self._users.get(user)

    def discardUserConnection(self, userOrConnection: UserConnection | User | str, *, discardPipeddConnections: bool = False):
        if isinstance(userOrConnection, UserConnection):
            userOrConnection = str(userOrConnection.user.id)

        if isinstance(userOrConnection, User):
            userOrConnection = str(userOrConnection.id)

        if userOrConnection not in self._users:
            raise ValueError("User not found")

        if (connection := self.getUserXRobotConnection(user=userOrConnection)):
            self.discardUserXRobotConnection(connection, disconnect=discardPipeddConnections)

        del self._users[userOrConnection]

    def discardRobotConnection(self, robotOrConnection: RobotConnection | Robot | str, *, discardPipeddConnections: bool = False):
        if isinstance(robotOrConnection, RobotConnection):
            robotOrConnection = str(robotOrConnection.robot.id)

        if isinstance(robotOrConnection, Robot):
            robotOrConnection = str(robotOrConnection.id)

        if robotOrConnection not in self._robots:
            raise ValueError("Robot not found")

        if (connection := self.getUserXRobotConnection(robot=robotOrConnection)):
            self.discardUserXRobotConnection(connection, disconnect=discardPipeddConnections)


        del self._robots[robotOrConnection]

    def getUserXRobotConnection(self, *, user: User | str | None = None, robot: Robot | str | None = None) -> UsersXRobotMapType | None:
        userConnection = self.getUserConnection(user) if user is not None else None
        robotConnection = self.getRobotConnection(robot) if robot is not None else None

        if userConnection is not None and robotConnection is not None:
            for connection in self._users_x_robot:
                if connection.user == userConnection and connection.robot == robotConnection:
                    return connection
        elif userConnection is not None:
            for connection in self._users_x_robot:
                if connection.user == userConnection:
                    return connection
        elif robotConnection is not None:
            for connection in self._users_x_robot:
                if connection.robot == robotConnection:
                    return connection

        return None

    def addUserXRobotConnection(self, userConnection: UserConnection, robotConnection: RobotConnection) -> UsersXRobotMapType:
        if self.getUserConnection(userConnection.user) is not userConnection:
            raise ValueError("User already connected")

        if self.getRobotConnection(robotConnection.robot) is not robotConnection:
            raise ValueError("Robot already connected")

        if (connection := self.getUserXRobotConnection(user=userConnection.user)) is not None:
            raise RobotInUseError(connection=connection)

        if (connection := self.getUserXRobotConnection(robot=robotConnection.robot)) is not None:
            raise RobotInUseError(connection=connection)

        connection = UsersXRobotMapType(user=userConnection, robot=robotConnection)
        self._users_x_robot.append(connection)
        return connection

    def discardUserXRobotConnection(self, connection: UsersXRobotMapType, *, disconnect: bool = False):
        if connection not in self._users_x_robot:
            raise ValueError("Connection not found")

        if connection.connected:
            if disconnect:
                connection.disconnect()
            else:
                raise RobotInUseError(connection)

        self._users_x_robot.remove(connection)


@functools.cache
def get_robot_connection_repository() -> RobotConnectionRepository:
    return RobotConnectionRepository()

RobotConnectionRepositoryDep = Annotated[RobotConnectionRepository, Depends(get_robot_connection_repository)]
