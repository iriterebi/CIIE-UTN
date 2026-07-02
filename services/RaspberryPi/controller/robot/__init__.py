from ..config import config as __config

if __config.mock_robot:
    from .robot_mock_controller import RobotMockController as RobotController
else:
    from .robot_controller import RobotController as RobotController

__all__ = ["RobotController"]
