1. ./start.sh
2. ./tmux-start.sh

## TROUBLESHOOTING
1. Error: sudo systemctl command not found, correr /root/.inorbit/dist/scripts/start.sh  --> esti es de inorbit
Si sigue sin funcionar, correr /root/.inorbit/dist/scripts/uninstall.sh y devuelta curlear.
Si sigue sin funcionar al curlear, correr 
'''bash
sudo cp /root/.inorbit/local/inorbit.service /etc/systemd/system
sudo systemctl enable inorbit.service
sudo systemctl start inorbit
'''
2. sudo: systemctl: command not found: ya estoy solucionandolo.
