import rclpy
from rclpy.node import Node
from my_interfaces.msg import Target


class TargetPublisher(Node):
    """按 10Hz 发布目标数据"""

    def __init__(self):
        super().__init__('target_publisher')          # 节点名，ros2 node list 会显示 /target_publisher
        self.pub = self.create_publisher(Target, 'target', 10)   # 10 = QoS 队列深度
        self.timer = self.create_timer(0.1, self.tick)          # 0.1 秒 = 10Hz
        self.count = 0
        self.get_logger().info('发布者已启动，10Hz 发布到 /target')

    def tick(self):
        msg = Target()
        msg.stamp = self.get_clock().now().to_msg()   # 必须用 ROS 时钟，不能用 time.time()
        msg.x = 1.0 + 0.01 * self.count
        msg.y = 2.0
        # 每 10 帧故意给一个低置信度，方便后面写订阅端的过滤逻辑
        msg.confidence = 0.2 if self.count % 10 == 3 else 0.95

        self.pub.publish(msg)

        # 每 10 帧打一条日志，避免刷屏
        if self.count % 10 == 0:
            self.get_logger().info(
                f'x={msg.x:.2f} y={msg.y:.2f} conf={msg.confidence:.2f}'
            )

        self.count += 1


def main(args=None):
    rclpy.init(args=args)
    node = TargetPublisher()
    try:
        rclpy.spin(node)          # 阻塞，事件循环在这里，回调靠它触发
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()       # 先销毁节点
        rclpy.shutdown()          # 再关闭上下文


if __name__ == '__main__':
    main()
