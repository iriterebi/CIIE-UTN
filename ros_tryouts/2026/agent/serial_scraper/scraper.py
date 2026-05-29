"""
Serial scraper node. Reads data from Arduino via serial and publishes to /inorbit/custom_data.
Also subscribes to /inorbit/custom_command and writes received commands back to serial.
"""
import os
import re
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
from dotenv import load_dotenv

load_dotenv()

SERIAL_PORT = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')
BAUD_RATE = int(os.getenv('BAUD_RATE', '9600'))

MODO_MAP = {
    'sweep_start':                    'barridoEnCurso',
    'sweep_end':                      'barridoCompletado',
    'sweep_aborted':                  'barridoAbortado',
    'experiment_restart':             'reinicio',
    'motor_stopped':                  'motorDetenido',
    'MRUV motor controller ready':    'listo',
}


class SerialScraper(Node):
    def __init__(self):
        super().__init__('serial_scraper_node')
        self.publisher_ = self.create_publisher(String, '/inorbit/custom_data', 10)
        self.subscription = self.create_subscription(String, '/inorbit/custom_command', self.command_callback, 10)
        self.ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        self.get_logger().info(f'Serial scraper started on {SERIAL_PORT} at {BAUD_RATE} baud')
        self.timer = self.create_timer(0.1, self.read_serial)
        self._modo = 'listo'
        self._pwm = 0
        self._tension = 0

    def command_callback(self, msg):
        line = msg.data.strip() + '\n'
        self.ser.write(line.encode('utf-8'))
        self.get_logger().info(f'Sent to serial: {msg.data}')

    def read_serial(self):
        if self.ser.in_waiting > 0:
            raw = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if not raw:
                return

            pwm_match = re.search(r'pwm=(\d+)', raw)
            tension_match = re.search(r'tension en gramos=(\d+)', raw)

            if raw in MODO_MAP:
                self._modo = MODO_MAP[raw]
            elif raw.startswith('t='):
                self._modo = 'enOperacion'
            elif pwm_match and not raw.startswith('t='):
                self._modo = 'barridoEnCurso'
            if pwm_match:
                self._pwm = int(pwm_match.group(1))
            if tension_match:
                self._tension = int(tension_match.group(1))

            for kv in [f'Modo={self._modo}', f'Tension={self._tension}', f'Velocidad={self._pwm}']:
                m = String()
                m.data = kv
                self.publisher_.publish(m)
            self.get_logger().info(f'Modo={self._modo} Tension={self._tension} Velocidad={self._pwm}')

    def destroy_node(self):
        self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = SerialScraper()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
