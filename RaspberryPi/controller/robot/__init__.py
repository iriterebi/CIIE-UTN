from ..config import MOCK_ROBOT as __MOCK_ROBOT

if __MOCK_ROBOT:
    from .robot_mock_controller import RobotMockController as RobotController
else:
    from .robot_controller import RobotController
