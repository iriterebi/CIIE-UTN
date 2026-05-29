#include <Arduino.h>


## TODO IRI: bajar el tiempo que tarda en sweep por muhco, para darle a inorbit tiempo, ver que devuelta el laser no frena el coso.  


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
static const uint8_t PIN_LASER = 2; 
static const uint8_t PIN_IR= 6; 
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

void setMotorSpeed(int pwm, bool forward = true);
void stopMotor();
void laserLogic();
bool delayWithLaserCheck(int ms);
void runSweep();
void experimentRestart();

// ───────────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(BAUD_RATE);

  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_IR, INPUT);

  stopMotor();

  Serial.println(F("MRUV motor controller ready"));
  Serial.println(F("Send value [0-10] + newline"));
  digitalWrite(PIN_LASER, HIGH);
}

// ───────────────────────────────────────────────────────────────────────────
void loop() {
  laserLogic();
  char line[SERIAL_BUFFER_SIZE];

  if (!readSerialLine(line)) {
    return;
  }

  if (strcmp(line, "start") == 0) {
    runSweep();
  } else if (strcmp(line, "restart") == 0) {
    experimentRestart();
  } else if (strcmp(line, "stop") == 0) {
    stopMotor();
    Serial.println(F("motor_stopped"));
  } else {
    if (line[0] == '-') {
      Serial.println(F("error=valor negativo no admitido"));
      return;
    }
    float value = parseAndClamp(line);
    int pwm = mapToPWM(value);
    setMotorSpeed(pwm, true);
    int tensionGramos = map(pwm, 80, 255, 50, 250);

    // ── Telemetría ────────────────────────────────────────────────────────
    Serial.print(F("t="));
    Serial.print(millis());
    Serial.print(F(" in="));
    Serial.print(value, 2);
    Serial.print(F(" pwm="));
    Serial.print(pwm);
    Serial.print(F(" tension en gramos="));
    Serial.println(tensionGramos);
  }
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
void setMotorSpeed(int pwm, bool forward = true) {

  if (pwm <= 0) {
    stopMotor();
    return;
  }

  if (forward) {
    digitalWrite(PIN_IN1, HIGH);
    digitalWrite(PIN_IN2, LOW);
  } else {
    digitalWrite(PIN_IN1, LOW);
    digitalWrite(PIN_IN2, HIGH);
  }

  analogWrite(PIN_ENA, pwm);
}

// ───────────────────────────────────────────────────────────────────────────
void stopMotor() {

  analogWrite(PIN_ENA, 0);

  // Freewheel/coast stop
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
}

void laserLogic() {
  int sensorValue = digitalRead(PIN_IR);

  if (sensorValue == LOW) {
    stopMotor();
    digitalWrite(PIN_LASER, LOW);
  }
}

// Waits ms milliseconds, checking IR every 20 ms.
// Returns false immediately if the laser is triggered.
bool delayWithLaserCheck(int ms) {
  for (int elapsed = 0; elapsed < ms; elapsed += 20) {
    if (digitalRead(PIN_IR) == LOW) {
      stopMotor();
      return false;
    }
    delay(20);
  }
  return true;
}

void runSweep() {
  Serial.println(F("sweep_start"));
  for (int pwm = 0; pwm <= 255; pwm += 5) {
    if (digitalRead(PIN_IR) == LOW) {
      stopMotor();
      Serial.println(F("sweep_aborted"));
      return;
    }
    setMotorSpeed(pwm, true);
    int tensionGramos = map(pwm, 80, 255, 50, 250);
    Serial.print(F("pwm="));
    Serial.print(pwm);
    Serial.print(F(" tension en gramos="));
    Serial.println(tensionGramos);
    if (!delayWithLaserCheck(1000)) {
      Serial.println(F("sweep_aborted"));
      return;
    }
  }
  if (digitalRead(PIN_IR) != LOW) {
    setMotorSpeed(255, true);
    int tensionGramos = map(255, 80, 255, 50, 250);
    Serial.print(F("pwm=255 tension en gramos="));
    Serial.println(tensionGramos);
    delayWithLaserCheck(600);
  }
  stopMotor();
  Serial.println(F("sweep_end"));
}

void experimentRestart()
{
  digitalWrite(PIN_LASER, LOW);
  setMotorSpeed(200, false);
  delay(200);
  stopMotor();
  Serial.println(F("experiment_restart"));
}