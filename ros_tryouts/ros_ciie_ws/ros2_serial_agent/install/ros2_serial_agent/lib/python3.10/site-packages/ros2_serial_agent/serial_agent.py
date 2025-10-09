import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
import threading


class SerialAgent(Node):
    def __init__(self):
        super().__init__('serial_agent')

        # Leer variables de entorno
        port = os.environ.get("USB_PORT")
        baud = os.environ.get("BAUDRATE")

        self.get_logger().info(f"Conectando a {port} con baudrate {baud}")

        try:
            self.ser = serial.Serial(port, baud, timeout=1)
        except Exception as e:
            self.get_logger().error(f"No se pudo abrir el puerto serie: {e}")
            self.ser = None

        # Publisher y Subscriber
        self.publisher_ = self.create_publisher(String, 'instruction', 10)
        self.subscription = self.create_subscription(
            String,
            'instruction',
            self.listener_callback,
            10
        )

        # Hilo para leer del puerto serie
        if self.ser:
            thread = threading.Thread(target=self.read_from_serial, daemon=True)
            thread.start()

    def listener_callback(self, msg):
        if self.ser:
            try:
                self.ser.write((msg.data + '\n').encode('utf-8'))
                self.get_logger().info(f"Enviado a serie: {msg.data}")
            except Exception as e:
                self.get_logger().error(f"Error escribiendo en serie: {e}")

    def read_from_serial(self):
        while rclpy.ok():
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if line:
                    msg = String()
                    msg.data = line
                    self.publisher_.publish(msg)
                    self.get_logger().info(f"Recibido de serie: {line}")
            except Exception as e:
                self.get_logger().error(f"Error leyendo del puerto serie: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = SerialAgent()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
