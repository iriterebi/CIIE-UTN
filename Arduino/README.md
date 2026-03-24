arduino-cli board list
arduino-cli compile --fqbn arduino:avr:uno hell_wold
sudo arduino-cli monitor -p /dev/ttyACM0 -c baudrate=9600
arduino-cli upload -p /dev/ttyACM0 --fqbn arduino:avr:uno hell_world 


Dar permiso de acceso al puerto:
sudo chmod 666 /dev/ttyACM0