# ROS 2 InOrbit Agent — 2026

ROS 2 agent that integrates with the InOrbit platform. Publishes sensor data from an Arduino via serial, streams camera frames, and receives commands from InOrbit.

## Components

| Component | Description |
|---|---|
| `agent/serial_scraper/scraper.py` | Reads serial data from Arduino, publishes to InOrbit; also receives commands from InOrbit and writes them to serial |
| `agent/listener.py` | Minimal test node — subscribes to `/inorbit/custom_command` and logs/writes to serial |
| `agent/camera/camera_node.py` | Captures USB camera frames and publishes them as ROS `Image` messages |
| `agent/publisher.py` | Dummy data publisher for testing (no hardware needed) |

## Docker

Build and run the ROS 2 Jazzy container from the `docker/` directory:

```bash
cd ros_tryouts/2026/docker
./build.sh       # builds the image (only needed once, or after Dockerfile changes)
./run.sh         # starts the container and drops you into a shell
```

`SOURCES` is automatically set to the repo root via `git rev-parse --show-toplevel`, so the entire CIIE-UTN repo is mounted inside the container at `/home/docker/dev`.

`ADDR` is automatically set to the host machine's primary IP via `hostname -I`.

To expose a specific SSH port on the host instead of a random one:

```bash
INORBIT_HOST_PORT=2222 ./run.sh
```

To enable display forwarding (e.g. RViz):

```bash
WITH_DISPLAY=1 ./run.sh
```

## Start

```bash
./start.sh
./tmux-start.sh
```

When done:

```bash
./stop.sh
```

## Useful ROS 2 commands

```bash
# Monitor incoming sensor data
ros2 topic echo /inorbit/custom_data

# Send a test incoming data manually
ros2 topic pub --once /inorbit/custom_data std_msgs/msg/String "data: 'your_command_here'"

# Send a test command manually
ros2 topic pub --once /inorbit/custom_command std_msgs/msg/String "data: 'your_command_here'"

# List all active topics
ros2 topic list | grep inorbit
```

## Camera setup

Plug in the USB camera, then find the device on the host:

```bash
ls /dev/video*
```

Use the lower-numbered entry (e.g. `/dev/video4`). Update `camera/.env`:

```
CAMERA_DEVICE=/dev/video4
```

Then source it:

```bash
set -a && source camera/.env && set +a
```

## Troubleshooting

**`sudo systemctl` not found inside Docker:**
Run directly:
```bash
/root/.inorbit/dist/scripts/start.sh
```
If it still fails, reinstall:
```bash
/root/.inorbit/dist/scripts/uninstall.sh
# then re-run the curl install command
```
If the service still won't start:
```bash
sudo cp /root/.inorbit/local/inorbit.service /etc/systemd/system
sudo systemctl enable inorbit.service
sudo systemctl start inorbit
```
