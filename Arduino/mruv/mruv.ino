/**
 * mruv.ino
 *
 * Reads a speed value [0.0 – 10.0] from serial (newline-terminated),
 * maps it to a PWM duty cycle [0 – 255], and drives an H-bridge motor
 * module accordingly.
 *
 * ── H-bridge wiring (L298N or compatible) ──────────────────────────────────
 *
 *   H-bridge pin │ Arduino pin │ Notes
 *   ─────────────┼─────────────┼──────────────────────────────────────────
 *   ENA          │     9       │ PWM speed control (must be PWM-capable)
 *   IN1          │     7       │ Direction bit A
 *   IN2          │     8       │ Direction bit B
 *   GND          │    GND      │ Common ground with Arduino
 *   12V / VCC    │   Ext. PSU  │ Motor supply (do NOT use Arduino 5 V rail)
 *
 * Direction is fixed to FORWARD (IN1=HIGH, IN2=LOW).
 * Send 0 to stop the motor cleanly.
 *
 * ── Serial protocol ────────────────────────────────────────────────────────
 *   Baud rate : 9600
 *   Format    : ASCII float, newline-terminated  (e.g. "7.5\n")
 *   Range     : [0, 10]  — values outside this range are clamped
 * ──────────────────────────────────────────────────────────────────────────
 */

#include <Arduino.h>

// ── Pin definitions ────────────────────────────────────────────────────────
static const uint8_t PIN_ENA = 9;   // PWM enable   — must be a PWM pin (~)
static const uint8_t PIN_IN1 = 7;   // Direction bit A
static const uint8_t PIN_IN2 = 8;   // Direction bit B

// ── Protocol / mapping constants ───────────────────────────────────────────
static const float    INPUT_MIN   = 0.0f;
static const float    INPUT_MAX   = 10.0f;
static const uint8_t  PWM_MIN     = 0;
static const uint8_t  PWM_MAX     = 255;
static const uint32_t BAUD_RATE   = 9600;

// ── Forward declarations ───────────────────────────────────────────────────
bool    readSerialLine(String &out);
float   parseAndClamp(const String &line);
uint8_t mapToPWM(float value);
void    setMotorSpeed(uint8_t pwm);
void    stopMotor();

// ──────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);

  stopMotor();

  Serial.println(F("MRUV motor controller ready."));
  Serial.println(F("Send a value [0-10] followed by newline."));
}

// ──────────────────────────────────────────────────────────────────────────
void loop() {
  String line;
  if (!readSerialLine(line)) return;

  float   value = parseAndClamp(line);
  uint8_t pwm   = mapToPWM(value);

  setMotorSpeed(pwm);

  // Echo back so the host can confirm receipt
  Serial.print(F("in="));
  Serial.print(value, 2);
  Serial.print(F(" pwm="));
  Serial.println(pwm);
}

// ── Function implementations ───────────────────────────────────────────────

/**
 * Reads one newline-terminated line from Serial into `out`.
 * Strips carriage-return and surrounding whitespace.
 *
 * @param out  Output string (populated on success).
 * @return     true when a non-empty line is ready, false otherwise.
 */
bool readSerialLine(String &out) {
  if (!Serial.available()) return false;

  out = Serial.readStringUntil('\n');
  out.trim();
  return out.length() > 0;
}

/**
 * Parses a float from `line` and clamps it to [INPUT_MIN, INPUT_MAX].
 *
 * @param line  Raw ASCII string received over serial.
 * @return      Clamped float value.
 */
float parseAndClamp(const String &line) {
  float value = line.toFloat();
  if (value < INPUT_MIN) return INPUT_MIN;
  if (value > INPUT_MAX) return INPUT_MAX;
  return value;
}

/**
 * Maps a value in [INPUT_MIN, INPUT_MAX] to a PWM byte [PWM_MIN, PWM_MAX].
 *
 * Uses a linear mapping:  pwm = value / INPUT_MAX * PWM_MAX
 *
 * @param value  Clamped input value.
 * @return       PWM duty cycle byte (0–255).
 */
uint8_t mapToPWM(float value) {
  return static_cast<uint8_t>((value / INPUT_MAX) * static_cast<float>(PWM_MAX));
}

/**
 * Drives the H-bridge at the given PWM duty cycle.
 * Direction is FORWARD (IN1=HIGH, IN2=LOW).
 * Passing pwm=0 delegates to stopMotor() to ensure both direction
 * pins are deasserted cleanly.
 *
 * @param pwm  Duty cycle [0–255].
 */
void setMotorSpeed(uint8_t pwm) {
  if (pwm == 0) {
    stopMotor();
    return;
  }

  digitalWrite(PIN_IN1, HIGH);  // FORWARD
  digitalWrite(PIN_IN2, LOW);
  analogWrite(PIN_ENA, pwm);
}

/**
 * Stops the motor by zeroing the PWM and deasserting both direction pins.
 * Leaves the H-bridge in a safe low-power idle state.
 */
void stopMotor() {
  analogWrite(PIN_ENA, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
}
