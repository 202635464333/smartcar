import math

import rclpy
from rclpy.node import Node
from sensor_interfaces.msg import SensorData


class SensorNode(Node):
    """节点A：模拟超声波传感器，10Hz 发布 /sensor_data"""

    def __init__(self):
        super().__init__('node_a_sensor')
        # 注意：话题名用相对名 sensor_data，不是 /sensor_data
        # 相对名才能在 M1-2 里被 namespace 隔离
        self.pub = self.create_publisher(SensorData, 'sensor_data', 10)
        self.create_timer(0.1, self.tick)          # 0.1 秒 = 10Hz
        self.n = 0
        self.get_logger().info('节点A 启动：10Hz 发布 sensor_data')

    def tick(self):
        msg = SensorData()
        msg.stamp = self.get_clock().now().to_msg()     # 用 ROS 时钟
        msg.unit = 'm'
        # 在 0.15 ~ 1.15 米之间来回摆动，保证会低于 0.3 触发报警
        msg.distance = 0.65 + 0.5 * math.sin(self.n * 0.05)
        # 每 20 帧塞一个超量程，制造"无效数据"
        msg.status = 1 if self.n % 20 == 10 else 0

        self.pub.publish(msg)

        if self.n % 10 == 0:
            self.get_logger().info(f'distance={msg.distance:.2f} status={msg.status}')
        self.n += 1


def main(args=None):
    rclpy.init(args=args)
    node = SensorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
