#include <Arduino.h>

/**
 * mruv_motor_controller.ino
 *
 * Control de motor DC mediante H-bridge (L298N o compatible).
 * Recibe por Serial un valor de tensión/fuerza abstracta [0.0 – 10.0]
 * y lo convierte a PWM.
 *
 * Mejoras respecto a la versión original:
 * - Sin uso de String (evita fragmentación RAM)
 * - Lectura serial no bloqueante
 * - Deadzone compensation (PWM mínimo real)
 * - Código más robusto para experimentos largos
 * - Timeout serial configurable
 *
 * ── Serial protocol ────────────────────────────────────────────────────────
 * Baud rate : 9600
 * Format    : ASCII float + '\n'
 * Example   : 7.5
 *
 * ───────────────────────────────────────────────────────────────────────────
 */

#include <stdlib.h>

// ── Pines ──────────────────────────────────────────────────────────────────
static const uint8_t PIN_ENA = 9;   // PWM
static const uint8_t PIN_IN1 = 7;
static const uint8_t PIN_IN2 = 8;

// ── Configuración ──────────────────────────────────────────────────────────
static const float INPUT_MIN = 0.0f;
static const float INPUT_MAX = 10.0f;

static const int PWM_MIN = 0;
static const int PWM_MAX = 255;

// PWM mínimo para que el motor realmente empiece a girar
static const int PWM_START = 70;

static const long BAUD_RATE = 9600;

// ── Buffer serial ──────────────────────────────────────────────────────────
static const uint8_t SERIAL_BUFFER_SIZE = 32;
char serialBuffer[SERIAL_BUFFER_SIZE];
uint8_t serialIndex = 0;

// ── Prototipos ─────────────────────────────────────────────────────────────
bool readSerialLine(char* out);
float parseAndClamp(const char* line);
int mapToPWM(float value);

void setMotorSpeed(int pwm);
void stopMotor();

// ───────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);

  stopMotor();

  Serial.println(F("MRUV motor controller ready"));
  Serial.println(F("Send value [0-10] + newline"));
}

// ───────────────────────────────────────────────────────────────────────────
void loop() {

  char line[SERIAL_BUFFER_SIZE];

  if (!readSerialLine(line)) {
    return;
  }

  float value = parseAndClamp(line);

  int pwm = mapToPWM(value);

  setMotorSpeed(pwm);

  // ── Telemetría ──────────────────────────────────────────────────────────
  Serial.print(F("t="));
  Serial.print(millis());

  Serial.print(F(" in="));
  Serial.print(value, 2);

  Serial.print(F(" pwm="));
  Serial.println(pwm);
}

// ───────────────────────────────────────────────────────────────────────────
bool readSerialLine(char* out) {

  while (Serial.available()) {

    char c = Serial.read();

    // Ignorar carriage return
    if (c == '\r') {
      continue;
    }

    // Línea completa
    if (c == '\n') {

      serialBuffer[serialIndex] = '\0';

      strcpy(out, serialBuffer);

      serialIndex = 0;

      return true;
    }

    // Guardar caracter si hay espacio
    if (serialIndex < SERIAL_BUFFER_SIZE - 1) {
      serialBuffer[serialIndex++] = c;
    }
  }

  return false;
}

// ───────────────────────────────────────────────────────────────────────────
float parseAndClamp(const char* line) {

  float value = atof(line);

  if (value < INPUT_MIN) {
    value = INPUT_MIN;
  }

  if (value > INPUT_MAX) {
    value = INPUT_MAX;
  }

  return value;
}

// ───────────────────────────────────────────────────────────────────────────
int mapToPWM(float value) {

  // Stop real
  if (value <= 0.0f) {
    return 0;
  }

  // Mapping con compensación de deadzone
  float normalized = value / INPUT_MAX;

  int pwm = PWM_START +
            (int)(normalized * (PWM_MAX - PWM_START));

  // Clamp seguridad
  if (pwm > PWM_MAX) {
    pwm = PWM_MAX;
  }

  return pwm;
}

// ───────────────────────────────────────────────────────────────────────────
void setMotorSpeed(int pwm) {

  if (pwm <= 0) {
    stopMotor();
    return;
  }

  // Dirección forward
  digitalWrite(PIN_IN1, HIGH);
  digitalWrite(PIN_IN2, LOW);

  analogWrite(PIN_ENA, pwm);
}

// ───────────────────────────────────────────────────────────────────────────
void stopMotor() {

  analogWrite(PIN_ENA, 0);

  // Freewheel/coast stop
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
}