# Serial Scraper

Reads string values from a serial port and publishes them to `/inorbit/custom_data` as `data_dummy=<value>`.

## 1. Find your serial port name

Plug in your device, then run:

```bash
ls /dev/tty*
```

Common names:
- `/dev/ttyUSB0` — USB-to-serial adapters (FTDI, CH340, etc.)
- `/dev/ttyACM0` — Arduino and similar USB CDC devices
- `/dev/ttyS0`   — built-in RS232 ports

To confirm which one is your device, check before and after plugging it in and see which entry appears.

You can also use:
```bash
dmesg | tail -20
```
and look for a line like `usb ... now attached to ttyUSB0`.

## 2. Set up the environment

Copy the example file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```
SERIAL_PORT=/dev/ttyUSB0   # port name from step 1
BAUD_RATE=9600              # must match your device's baud rate
```

## 3. Run

Make sure ROS 2 is sourced, then:

```bash
source /opt/ros/humble/setup.bash
python3 scraper.py
```

The node will read each line from the serial port and publish it to InOrbit as `data_dummy=<value>`.
