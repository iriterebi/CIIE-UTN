#include <Arduino.h>

static const uint8_t PIN_LASER = 2;
static const uint8_t PIN_IR = 6;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_LASER, OUTPUT);
  pinMode(PIN_IR, INPUT_PULLUP);
  digitalWrite(PIN_LASER, HIGH);
  Serial.println(F("IR sensor test — reading every 100ms"));
}

void loop() {
  int val = digitalRead(PIN_IR);
  Serial.print(F("t="));
  Serial.print(millis());
  Serial.print(F(" ir="));
  Serial.println(val == HIGH ? "HIGH (triggered)" : "LOW (clear)");
  delay(100);
}
