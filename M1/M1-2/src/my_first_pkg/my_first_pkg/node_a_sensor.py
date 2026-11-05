"""节点A：模拟一个超声波传感器，每 0.1 秒造一条 Distance 数据发出去。

在链路里的位置：
    【节点A】 --/sensor_data--> 节点B --/processed_distance--> 节点C

本文件分四段：
    第1段  import + 定义类    —— 准备工具
    第2段  __init__           —— 登记：往哪个话题发、多久发一次
    第3段  tick               —— 被定时器叫起来，每次造一条数据发出去
    第4段  main               —— 标准启动流程
"""

# ============ 第 1 段 ============

import math                           # 为了用 sin() 造一个忽远忽近的距离

import rclpy
from rclpy.node import Node
from sensor_interfaces.msg import SensorData   # 消息定义在自己建的接口包里


class SensorNode(Node):
    """继承 Node，就有了 create_publisher / create_timer 这些能力。"""

    # ============ 第 2 段：登记"往哪发、多久发一次" ============

    def __init__(self):
        # 节点名，会显示成 /node_a_sensor
        super().__init__('node_a_sensor')

        # 建发布者：往 'sensor_data' 话题发 SensorData 类型，队列深度 10。
        # ★ 注意话题名写的是 'sensor_data'，不是 '/sensor_data'（前面没斜杠）。
        #   这叫"相对名"——加命名空间时会自动变成 /robot1/sensor_data。
        #   写成绝对名 '/sensor_data' 的话，会绕过命名空间，M1-2 两组就撞一起了。
        self.pub = self.create_publisher(SensorData, 'sensor_data', 10)

        # 建定时器：每 0.1 秒调用一次 self.tick。
        # ★ 这里只是"登记"，不会立刻执行——真正开始叫，是在 main 里 spin 之后。
        #   0.1 秒 = 每秒 10 次 = 10Hz。
        self.create_timer(0.1, self.tick)

        self.n = 0      # 帧计数器，用来造波动和打日志

        self.get_logger().info('节点A 启动：10Hz 发布 sensor_data')

    # ============ 第 3 段：每 0.1 秒被叫一次，造数据发出去 ============

    def tick(self):
        # 造一条空消息（所有字段都是默认值：数字是 0，字符串是空）
        msg = SensorData()

        # 填时间戳。★ 用 ROS 自己的时钟（self.get_clock()），不用 Python 的 time.time()。
        #   因为回放 bag 时 ROS 时钟可以变成"仿真时间"，跟真实时间不一样。
        msg.stamp = self.get_clock().now().to_msg()

        # 单位，题目要求固定 "m"
        msg.unit = 'm'

        # 距离：用正弦波在 0.15 ~ 1.15 米之间来回摆。
        #   0.65 是中心值，0.5 是摆幅，sin 的取值范围是 -1~1。
        #   这么造是为了让距离一定会低于 0.3，好触发下游的报警。
        msg.distance = 0.65 + 0.5 * math.sin(self.n * 0.05)

        # 状态：每 20 帧里有 1 帧标成 1（超出量程），用来测试下游的过滤逻辑。
        #   % 20 == 10 表示"第 10、30、50… 帧"
        msg.status = 1 if self.n % 20 == 10 else 0

        # 发出去。publish 是"扔进队列就返回"，不等别人收到。
        self.pub.publish(msg)

        # 每 10 帧打一行日志，避免刷屏
        if self.n % 10 == 0:
            self.get_logger().info(
                f'distance={msg.distance:.2f} status={msg.status}')
        self.n += 1

    # ============ 第 4 段：标准启动流程 ============


def main(args=None):
    rclpy.init(args=args)
    node = SensorNode()

    try:
        rclpy.spin(node)        # 进入事件循环。定时器到点了，spin 会叫 tick
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
