# /Arduino · Robot Firmware

> **Español**: [README.es.md](README.es.md)

Native firmware for the robotic arm. Runs on an Arduino board and controls 7 servos via PWM signals.

## Hardware

The robotic arm consists of 7 servo motors, each controlling a different joint:

| Servo | Pin | Description |
|-------|-----|-------------|
| Base | 3 | Rotates the entire arm |
| Cuerpo (Body) | A0 | Controls the body/torso |
| Hombro (Shoulder) | 6 | Shoulder joint |
| Brazo (Arm) | 9 | Upper arm movement |
| Antebrazo1 (Forearm 1) | 10 | Forearm movement (axis 1) |
| Antebrazo2 (Forearm 2) | 5 | Forearm movement (axis 2) |
| Mano (Hand) | 11 | Gripper / hand |

## How It Works

The firmware exposes individual movement functions per servo (`moverBase`, `moverMano`, etc.) and a combined function `moverBrazo` that positions all 7 servos at once. Each function receives an angle (0–180°) and writes it to the corresponding servo.

The `loop()` currently runs a simple test sequence, moving each servo to 20° with a 1-second delay between movements.

## Communication

In the full system, the RaspberryPi sends serial commands to the Arduino to control the arm. The Pi receives commands from the API via ROS/RosBridge and translates them into serial instructions for the Arduino.

```
[API] → [RosBridge/ROS] → [RaspberryPi] → [Serial] → [Arduino] → [Servos]
```

## Dependencies

- [Servo.h](https://www.arduino.cc/reference/en/libraries/servo/) — Standard Arduino library for PWM servo control

## Tools

- [Arduino IDE](https://www.arduino.cc/en/software) — Official graphical IDE for writing, compiling, and uploading sketches
- [Arduino CLI](https://arduino.github.io/arduino-cli/) — Command-line tool for compiling and uploading without the IDE

## Files

> `.ino` is the file format used by the [Arduino IDE](https://www.arduino.cc/en/software). It is essentially C/C++ — the IDE automatically includes `Arduino.h` at compile time. Every sketch requires two functions: `setup()` (runs once on power-up) and `loop()` (runs repeatedly).
