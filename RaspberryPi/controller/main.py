#!/usr/bin/env python3

"""
TODO

ROS bridege
"""

import logging
import sys
from .config import ARDUINO_PORT, CREATE_DEFAULT_METADATA
from .server.server_service import ServerServices
from .robot import RobotController


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout,
    )

    logger = logging.getLogger(__name__)

    service = ServerServices()

    if not service.load_external_config() and CREATE_DEFAULT_METADATA:
        service.create_default_config()


    robot = RobotController(ARDUINO_PORT)


    with service, robot:
        service.get_commands(
            robot.send_command
        )

        # logger.info("Data received from server: %s", data)

        # robot.execute_sequence(data)
