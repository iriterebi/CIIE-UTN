import os
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial
import threading
from rclpy.timer import Timer

class SerialAgent(Node):
    def __init__(self):
        super().__init__('serial_agent')

        # --- Variables de Estado del Protocolo ---
        # is_publishing: Controla si estamos en el "modo de espera de 2s" (pub=true)
        # last_instruction: Almacena la instrucción recibida para el puerto serie
        self.is_publishing = False
        self.last_instruction = "none"
        self.publish_counter = 0  # Contador para el timeout de 2 segundos

        # --- Configuración del Puerto Serie ---
        # Obtener el puerto de la variable de entorno
        port = os.environ.get('SERIAL_PORT', '/dev/ttyACM0') 
        baud = 115200

        self.get_logger().info(f"Conectando a {port} con baudrate {baud}")

        try:
            # Configuración del puerto serie
            self.ser = serial.Serial(port, baud, timeout=0.1)
            self.ser.flush()
        except Exception as e:
            self.get_logger().error(f"No se pudo abrir el puerto serie: {e}")
            self.ser = None

        # --- Publishers y Subscribers ---
        # Publisher para el estado y la instrucción de salida
        self.publisher_ = self.create_publisher(String, '/inorbit/custom_data/0', 10)
        
        # Subscriber para las instrucciones entrantes (desde ROS)
        self.subscription = self.create_subscription(
            String,
            '/inorbit/custom_data/0',
            self.listener_callback,
            10
        )
        self.get_logger().info('Agente Serial ROS 2 iniciado y listo.')
        
        # --- Timers y Threads ---
        # Timer no bloqueante para manejar el timeout de 2 segundos
        # Se ejecuta 10 veces por segundo (100ms) para una resolución de 2 segundos (20 ticks)
        self.status_timer = self.create_timer(0.1, self.status_timer_callback)

        # Hilo para leer del puerto serie (si la conexión fue exitosa)
        if self.ser:
            thread = threading.Thread(target=self.read_from_serial, daemon=True)
            thread.start()

    # --- LÓGICA DEL PROTOCOLO DE ESTADO ---
    def status_timer_callback(self):
        """
        Gestiona el timeout de 2 segundos después de enviar una instrucción.
        Equivalente a (pub=true, esperar 2s, pub=false, $instruccion=none)
        """
        if self.is_publishing:
            self.publish_counter += 1
            
            # Condición 1: Publicar pub=true inmediatamente al iniciar el conteo
            if self.publish_counter == 1:
                self.publisher_.publish(String(data="pub=true"))
                self.get_logger().info("Publicando estado: pub=true")

            # Condición 2: Timeout de 2 segundos (20 ticks de 100ms)
            if self.publish_counter >= 20:
                # 1. Publicar pub=false
                self.publisher_.publish(String(data="pub=false"))
                self.get_logger().info("Publicando estado: pub=false. Timeout completado.")
                
                # 2. Resetear estado
                self.is_publishing = False
                self.publish_counter = 0
                self.last_instruction = "none" # $instruccion = none

    # --- LÓGICA DE RECEPCIÓN DE ROS 2 ---
    def listener_callback(self, msg):
        """
        Maneja los mensajes recibidos en /inorbit/custom_data/0.
        """
        # Intentamos obtener la instrucción del mensaje
        data = msg.data.strip()
        
        # Caso 1: Lectura de Instrucción (simula tu pub=false y $instruction != none)
        # Buscamos el prefijo 'instruction=' y verificamos el estado
        if data.startswith("instruction=") and data != "instruction=none":
            
            received_instruction = data.split("instruction=")[1].strip()
            
            # Si NO estamos publicando (is_publishing=False), procesamos la instrucción
            if not self.is_publishing:
                self.last_instruction = received_instruction

                if self.ser:
                    try:
                        # 1. Enviar al puerto serie
                        self.ser.write((self.last_instruction + '\n').encode('utf-8'))
                        self.get_logger().info(f"Enviado a serie: {self.last_instruction}")
                        
                        # 2. Activar la lógica de publicación de estado (pub=true, sleep, pub=false)
                        self.is_publishing = True
                        self.publish_counter = 0 # Reiniciar el contador del timer
                        
                    except Exception as e:
                        self.get_logger().error(f"Error escribiendo en serie: {e}")
            else:
                self.get_logger().warn("Instrucción ignorada: Agente ocupado (is_publishing=True).")
        
        # Caso 2: Ignorar mensajes de estado propios ('pub=true' o 'pub=false')
        # Esto evita que el nodo entre en un loop al escucharse a sí mismo.
        elif data.startswith("pub="):
            return

    # --- LÓGICA DE LECTURA SERIAL ---
    def read_from_serial(self):
        """Lee datos del puerto serie en un hilo separado."""
        while rclpy.ok():
            try:
                # Usamos readline() y strip() para limpiar la entrada
                line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    # Publica lo recibido del Arduino
                    msg = String()
                    msg.data = f"serial_in={line}"
                    self.publisher_.publish(msg)
                    self.get_logger().info(f"Recibido de serie: {line}")
            except serial.SerialTimeoutException:
                # Esto es normal con timeout=0.1
                continue
            except Exception as e:
                self.get_logger().error(f"Error leyendo del puerto serie: {e}")
                # Pausamos el loop un momento para evitar un consumo excesivo de CPU
                # Si el error es grave y repetitivo, el thread fallará.
                # Ya que estamos en un thread, podemos usar time.sleep()
                import time
                time.sleep(1)


def main(args=None):
    rclpy.init(args=args)
    node = SerialAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
