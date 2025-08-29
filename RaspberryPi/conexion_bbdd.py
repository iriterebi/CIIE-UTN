#!/usr/bin/env python3

import os
import requests
import serial
import time
import config
from server_service import ServerServices
from robot_controller import RobotController
import sys


if __name__ == "__main__":
    service = ServerServices()

    with RobotController(config.ARDUINO_PORT) as robot:
        data = service.get_commands()

        print("data recieved from server:")
        print(data, file=sys.stderr)

        robot.execute_sequence(data)
