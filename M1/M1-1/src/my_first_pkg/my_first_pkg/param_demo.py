import rclpy
from rclpy.node import Node


class ParamDemo(Node):

    def __init__(self):
        super().__init__('param_demo')

        # ① 声明一个参数：名字叫 alpha，默认值 0.3
        self.declare_parameter('alpha', 0.3)

        # 每 1 秒打印一次
        self.create_timer(1.0, self.tick)

    def tick(self):
        # ② 每次现读一遍（不是启动时读一次），所以外面改了能立刻看到
        alpha = self.get_parameter('alpha').value
        self.get_logger().info(f'alpha = {alpha}')


def main(args=None):
    rclpy.init(args=args)
    node = ParamDemo()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
