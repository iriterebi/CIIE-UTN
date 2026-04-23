import os
import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

CAMERA_DEVICE = os.getenv('CAMERA_DEVICE', '/dev/video0')


class CameraNode(Node):
    def __init__(self):
        super().__init__('camera_node')
        self.publisher_ = self.create_publisher(Image, 'usb_cam/image_raw', 10)

        device_index = self._device_index(CAMERA_DEVICE)
        self.cap = cv2.VideoCapture(device_index)
        if not self.cap.isOpened():
            self.get_logger().error(f'Could not open camera at {CAMERA_DEVICE}')
            raise RuntimeError(f'Camera not available: {CAMERA_DEVICE}')

        self.get_logger().info(f'Camera node started on {CAMERA_DEVICE}')
        self.timer = self.create_timer(0.033, self.publish_frame)  # ~30 fps

    def _device_index(self, device_path: str) -> int:
        try:
            return int(device_path.replace('/dev/video', ''))
        except ValueError:
            return 0

    def publish_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn('Failed to capture frame')
            return
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = frame.shape
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.height = h
        msg.width = w
        msg.encoding = 'rgb8'
        msg.is_bigendian = False
        msg.step = w * 3
        msg.data = frame.tobytes()
        self.publisher_.publish(msg)

    def destroy_node(self):
        self.cap.release()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = CameraNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
