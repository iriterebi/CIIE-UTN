#include <Servo.h> 

// Crear una instancia para cada servo
Servo servoBase;
Servo servoCuerpo;
Servo servoHombro;
Servo servoBrazo;
Servo servoAntebrazo1;
Servo servoAntebrazo2;
Servo servoMano;

// Pines a los que está conectado cada servo
const int pinBase = 3;
const int pinCuerpo = A0;
const int pinHombro = 6;
const int pinBrazo = 9;
const int pinAntebrazo1 = 10;
const int pinAntebrazo2 = 5;
const int pinMano = 11;


void setup() {
  // Asignar cada servo a su pin correspondiente
  servoBase.attach(pinBase);
  servoCuerpo.attach(pinCuerpo);
  servoHombro.attach(pinHombro);
  servoBrazo.attach(pinBrazo);
  servoAntebrazo1.attach(pinAntebrazo1);
  servoAntebrazo2.attach(pinAntebrazo2);
  servoMano.attach(pinMano);


}

void moverMano(int mano)
{
    servoMano.write(mano);
}
void moverHombro(int hombro)
{
    servoHombro.write(hombro);
}
void moverBase(int base)
{
    servoBase.write(base);
}
void moverBrazo(int Brazo)
{
    servoBrazo.write(Brazo);
}
void moverAntebrazo1(int Antebrazo1)
{
    servoAntebrazo1.write(Antebrazo1);
}
void moverAntebrazo2(int Antebrazo2)
{
    servoAntebrazo2.write(Antebrazo2);
}
void moverCuerpo(int Cuerpo)
{
    servoCuerpo.write(Cuerpo);
}


void moverBrazo(int base, int cuerpo, int hombro, int brazo, int antebrazo1, int antebrazo2, int mano) {
  
  servoBase.write(base);
  servoCuerpo.write(cuerpo);
  servoHombro.write(hombro);
  servoBrazo.write(brazo);
  servoAntebrazo1.write(antebrazo1);
  servoAntebrazo2.write(antebrazo2);
  servoMano.write(mano);
}

void loop() {

  moverMano(20); 
  delay(1000);

  moverAntebrazo1(20);
  delay(1000);

  moverAntebrazo2(20);
  delay(1000);

  moverBrazo(20);
  delay(1000);

  moverHombro(20); 
  delay(1000);

  moverCuerpo(20);
  delay(1000);

  moverBase(20); 
  delay(1000);


}
