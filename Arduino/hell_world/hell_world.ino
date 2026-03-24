int count = 0;
void setup() {
  Serial.begin(9600);
  
}

void loop() {
  Serial.println(String(count)); 
  digitalWrite(13,!digitalRead(13));
  count++;
  delay(500); // 2 veces por segundo
}