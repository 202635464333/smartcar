"""节点A：模拟超声波传感器，每 0.1 秒造一条距离数据发出去。

链路位置：
    【节点A】 --/sensor_data--> 节点B --/processed_distance--> 节点C

四段结构：
    第1段  import + 定义类   准备工具
    第2段  __init__          登记：往哪个话题发、多久发一次
    第3段  tick              被定时器叫起来，造一条数据发出去
    第4段  main              标准启动流程
"""

# ==================== 第 1 段：拿工具 ====================

import math                                         # 数学库，为了用 sin() 造忽远忽近的距离

import rclpy                                        # ROS2 客户端库
from rclpy.node import Node                         # 节点父类
from sensor_interfaces.msg import SensorData        # 自定义消息（4 个字段）


class SensorNode(Node):                             # 继承 Node，就有了 create_publisher / create_timer
    """节点A：10Hz 发布 SensorData"""

    # ==================== 第 2 段：登记"往哪发、多久发一次" ====================

    def __init__(self):                             # 造节点时自动执行
        super().__init__('node_a_sensor')           # 登记节点名，ros2 node list 显示 /node_a_sensor

        self.pub = self.create_publisher(           # 建发布者
            SensorData,                             # 发 SensorData 类型
            'sensor_data',                          # 话题名用相对名（无斜杠）
                                                    # ★ 相对名才能被命名空间隔离成 /robot1/sensor_data
                                                    #   写成 '/sensor_data' 会绕过命名空间，M1-2 两组会串数据
            10)                                     # 队列深度 10（发布者与订阅者之间信息缓冲的容量）

        self.create_timer(0.1, self.tick)           # 定时器：每 0.1 秒调用一次 tick（0.1s = 10Hz）
                                                    # ★ 这里只是"登记"，真正开始叫是 spin 之后

        self.n = 0                                  # 帧计数器，用来造波动、控制日志频率

        self.get_logger().info('节点A 启动：10Hz 发布 sensor_data')

    # ==================== 第 3 段：定时器每叫一次，造一条数据 ====================

    def tick(self):                                 # 每 0.1 秒执行一次
        msg = SensorData()                          # 造一条空消息（字段都是默认值）

        msg.stamp = self.get_clock().now().to_msg()
                                                    # 填时间戳；用 ROS 时钟而非 time.time()
                                                    # ★ 回放 bag 时 ROS 时钟可变成仿真时间(与小车时间同步)，与真实时间不同

        msg.unit = 'm'                              # 单位，题目要求固定 "m"

        msg.distance = 0.65 + 0.5 * math.sin(self.n * 0.05)
                                                    # 距离 = 中心 0.65 + 幅度 0.5 × sin(...)
                                                    # 范围 0.15~1.15 米，保证会掉到 0.3 以下触发报警

        msg.status = 1 if self.n % 20 == 10 else 0  # 状态：每 20 帧里塞 1 帧"超量程(1)"，用来测下游过滤
                                                    # 其余 19 帧都是 0（正常）

        self.pub.publish(msg)                       # 发出去；publish 扔进队列就返回，不等谁收到

        if self.n % 10 == 0:                        # 每 10 帧打一次日志，避免每秒 10 行刷屏
            self.get_logger().info(
                f'distance={msg.distance:.2f} status={msg.status}')

        self.n += 1                                 # 计数加一，供下次造数据用

    # ==================== 第 4 段：标准启动流程 ====================


def main(args=None):                                # 程序入口
    rclpy.init(args=args)                           # ① 启动 ROS
    node = SensorNode()                             # ② 造节点（执行上面的 __init__）

    try:                                            # ③ 捕获 Ctrl+C
        rclpy.spin(node)                            # 卡在这；定时器到点了 spin 会叫 tick
    except KeyboardInterrupt:                       # ④ 用户按 Ctrl+C
        pass                                        # 安静退出，不吐报错
    finally:                                        # ⑤ 无论如何都执行
        node.destroy_node()                         # 销毁节点
        rclpy.shutdown()                            # 关闭 ROS


if __name__ == '__main__':                          # 直接运行本文件才执行 main
    main()
