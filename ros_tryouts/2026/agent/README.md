Agent test:
Test for publishing:

## start publishing
python3 publisher.py   

##python3 listener.py

AL TERMINAR USAR ./stop.sh

Si no tenes el arduino comenta linea 12 y linea 16 de tmux-start.sh

ros2 topic echo /inorbit/custom_data 

ros2 topic pub --once /inorbit/custom_command std_msgs/msg/String "data: 'your_command_here'"

## Camera setup

Plug in the USB camera, then run on the **host** to find the device:

```bash
ls /dev/video*
```

You will see one or two new entries (e.g. `/dev/video4` and `/dev/video5`). Use the lower-numbered one.

Update `camera/.env`:

```
CAMERA_DEVICE=/dev/video4   # replace with your actual device
```

Then source it so the variable is available in your shell:

```bash
set -a && source camera/.env && set +a
```

