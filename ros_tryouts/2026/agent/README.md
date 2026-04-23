# Agent

ROS 2 nodes that bridge the robot hardware and the InOrbit platform.

## Files

| File | Description |
|---|---|
| `serial_scraper/scraper.py` | Main production node. Reads serial data from Arduino and publishes to `/inorbit/custom_data`. Also subscribes to `/inorbit/custom_command` and writes commands to serial. |
| `listener.py` | Test/debug node. Subscribes to `/inorbit/custom_command` and writes received commands to serial. Use this to verify the command pipeline without running the full scraper. |
| `publisher.py` | Dummy node that publishes fake sensor data to `/inorbit/custom_data`. Use this to test the InOrbit data pipeline without hardware. |
| `camera/camera_node.py` | Captures frames from a USB camera and publishes to `usb_cam/image_raw`. |

## Running manually

```bash
source /opt/ros/humble/setup.bash

# Serial scraper (production)
cd serial_scraper && python3 scraper.py

# Command listener (testing only)
python3 listener.py

# Dummy publisher (testing without hardware)
python3 publisher.py

# Camera
cd camera && python3 camera_node.py
```

> **Note:** `listener.py` and `scraper.py` both open the serial port. Do not run them at the same time.
