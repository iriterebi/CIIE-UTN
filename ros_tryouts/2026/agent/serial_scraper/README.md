# Serial Scraper

ROS 2 node that owns the serial connection to the Arduino. It handles both directions:

- **Arduino → InOrbit:** reads lines from serial, publishes to `/inorbit/custom_data` as `data_dummy=<value>`
- **InOrbit → Arduino:** subscribes to `/inorbit/custom_command`, writes received commands to serial

## 1. Find your serial port

Plug in your device, then run:

```bash
ls /dev/tty*
```

Common names:
- `/dev/ttyUSB0` — USB-to-serial adapters (FTDI, CH340, etc.)
- `/dev/ttyACM0` — Arduino and similar USB CDC devices
- `/dev/ttyS0`   — built-in RS232 ports

To confirm which one is yours, check before and after plugging in:
```bash
dmesg | tail -20
```
Look for a line like `usb ... now attached to ttyUSB0`.

## 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:

```
SERIAL_PORT=/dev/ttyUSB0   # port from step 1
BAUD_RATE=9600              # must match your Arduino sketch
```

## 3. Run

```bash
source /opt/ros/humble/setup.bash
python3 scraper.py
```

> Do not run `listener.py` at the same time — both nodes open the same serial port.
