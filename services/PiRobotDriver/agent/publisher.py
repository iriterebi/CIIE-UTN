"""
Dummy publisher node. Publishes fake fluctuating sensor data to /inorbit/custom_data.
Use this to test the InOrbit data pipeline without any hardware connected.
"""
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import random

class Publisher(Node):
    def __init__(self):
        super().__init__('agente_serial_node')
        self.publisher_ = self.create_publisher(String, '/inorbit/custom_data', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.get_logger().info('Nodo Publicador Dummy Iniciado')

    def timer_callback(self):
        # dummy simulado de dato fluctuante
        msg = String()
        msg.data = f"data_dummy={round(random.uniform(20.0, 30.0), 2)}"
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publicando: {msg.data}')

def main(args=None):
    rclpy.init(args=args)
    node = Publisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()