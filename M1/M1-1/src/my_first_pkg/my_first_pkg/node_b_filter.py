import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from sensor_interfaces.msg import SensorData


class FilterNode(Node):
    """节点B：一阶低通滤波，alpha 可用 ros2 param set 运行时改"""

    def __init__(self):
        super().__init__('node_b_filter')

        # 参数：必须 declare 才能被 ros2 param set 改
        self.declare_parameter('alpha', 0.3)

        self.sub = self.create_subscription(SensorData, 'sensor_data', self.on_data, 10)
        self.pub = self.create_publisher(Float32, 'processed_distance', 10)

        self.y = None        # 上一帧的滤波结果，第一帧时还没有
        self.count = 0
        self.get_logger().info('节点B 启动：一阶低通，alpha 默认 0.3')

    def on_data(self, msg):
        # ① 无效数据不参与滤波，但要打警告
        if msg.status != 0:
            self.get_logger().warn(
                f'丢弃无效数据 status={msg.status} distance={msg.distance:.2f}')
            return

        # ② 每次现读参数，这样外部改了立刻生效
        alpha = self.get_parameter('alpha').value

        # ③ 一阶低通：y = alpha*x + (1-alpha)*y_prev
        if self.y is None:
            self.y = msg.distance         # 第一帧没有"上次"，直接用原值
        else:
            self.y = alpha * msg.distance + (1 - alpha) * self.y

        self.pub.publish(Float32(data=float(self.y)))

        self.count += 1
        if self.count % 10 == 0:
            self.get_logger().info(f'滤波后={self.y:.3f}（alpha={alpha}）')


def main(args=None):
    rclpy.init(args=args)
    node = FilterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
