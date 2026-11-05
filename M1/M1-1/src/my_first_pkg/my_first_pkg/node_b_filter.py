"""节点B：把收到的距离做一阶低通滤波，再转发给下游。

链路位置：
    节点A --/sensor_data--> 【节点B】 --/processed_distance--> 节点C

四段结构：
    第1段  import + 定义类    准备工具
    第2段  __init__           造节点时登记：听谁、说给谁、记住什么
    第3段  on_data            每收到一条消息就跑一次（核心逻辑）
    第4段  main               标准启动流程，四个节点完全一样
"""

# ==================== 第 1 段：拿工具表 ====================

import rclpy                                        # ROS2 的 Python 客户端库，所有节点都要它
from rclpy.node import Node                         # Node 是父类，继承它才有 create_publisher 等能力
from std_msgs.msg import Float32                    # 标准消息：只装一个小数（发出去用）
from sensor_interfaces.msg import SensorData        # 自定义消息：4 个字段（收进来用）


class FilterNode(Node):
    """继承 Node，等于"我造一个新型号的节点"。
    括号里的 Node 就是继承：FilterNode 自动拥有 Node 的全部能力。
    """

    # ==================== 第 2 段：造节点时，把该登记的登记好 ====================

    def __init__(self):                             # 节点一被创建，这个函数就自动执行一次
        super().__init__('node_b_filter')           # 把节点名交给父类 Node，向 ROS 注册（ros2 node list 显示 /node_b_filter）
                                                    # 必须放第一句——先注册，才能往下用

        self.declare_parameter('alpha', 0.3)         # 声明参数 alpha=0.3；不声明的话 ros2 param set 会报 has not been declared

        self.sub = self.create_subscription(        # 建订阅者（收信口）
            SensorData,                             # 收什么类型的消息
            'sensor_data',                          # 从哪个话题收（相对名，加命名空间会自动变 /robot1/sensor_data）
            self.on_data,                           # 收到就调用这个函数
            10)                                     # 队列深度：最多先缓存 10 条，满了丢最旧的

        self.pub = self.create_publisher(           # 建发布者（寄信口）
            Float32,                                # 发什么类型：只有一个小数
            'processed_distance',                   # 往哪个话题发
            10)                                     # 队列深度

        self.y = None                               # 记住"上一次的滤波结果"；第一帧时还没有，所以是 None
        self.count = 0                              # 帧计数器，只为控制日志频率（每 10 帧打一次，避免刷屏）

        self.get_logger().info('节点B 启动：一阶低通，alpha 默认 0.3')   # 启动时打一行提示

    # ==================== 第 3 段：每收到一条消息就跑一次（核心） ====================

    def on_data(self, msg):                         # msg = 收到的那条 SensorData，含 distance/unit/stamp/status
        if msg.status != 0:                         # 状态：0 正常、1 超量程、2 传感器错误；非 0 即无效数据
            self.get_logger().warn(                 # 打黄色警告，说明丢了什么
                f'丢弃无效数据 status={msg.status} distance={msg.distance:.2f}')
            return                                  # 直接结束，不滤波、不发布
                                                    # ★ 必须放在滤波之前：否则坏数据会污染 self.y，后面几帧都跟着歪

        alpha = self.get_parameter('alpha').value   # 每次现读参数，外部改了下一帧立刻生效（不是启动时读一次）
                                                    # .value 才是真正的数值，get_parameter 返回的是包装对象

        if self.y is None:                          # 第一次收到数据，没有"上一次"可以套公式
            self.y = msg.distance                   # 直接拿原值作为第一次的滤波结果
        else:                                       # 从第二帧开始才能算
            self.y = alpha * msg.distance + (1 - alpha) * self.y
                                                    # 一阶低通：y = α·x + (1-α)·y_prev
                                                    # α 小（0.1）→ 平滑但滞后；α 大（0.9）→ 跟随快但跳动大

        self.pub.publish(Float32(data=float(self.y)))
                                                    # 装进 Float32 信封发出去；float() 保证是标准 Python 小数，避免 numpy 类型报错
                                                    # publish 是"扔进队列就返回"，不等任何人收到

        self.count += 1                             # 计数加一
        if self.count % 10 == 0:                    # 每满 10 帧才进一次（取余为 0）
            self.get_logger().info(f'滤波后={self.y:.3f}（alpha={alpha}）')
                                                    # :.3f 表示只显示 3 位小数

    # ==================== 第 4 段：标准启动流程（四个节点一模一样） ====================


def main(args=None):                                # 程序入口
    rclpy.init(args=args)                           # ① 启动 ROS 客户端库（不写这句，下面全用不了）
    node = FilterNode()                             # ② 造节点（这一行会执行上面的 __init__）

    try:                                            # ③ 包起来，为了捕获 Ctrl+C
        rclpy.spin(node)                            # 卡在这里等消息；每来一条 sensor_data 就替我们调一次 on_data
    except KeyboardInterrupt:                       # ④ 用户按 Ctrl+C 时触发
        pass                                        # 什么都不做，安静退出（不写就会吐红色报错）
    finally:                                        # ⑤ 不管上面怎么结束，这里都必做
        node.destroy_node()                         # 先销毁节点（从 ROS 注销）
        rclpy.shutdown()                            # 再关闭客户端库


if __name__ == '__main__':                          # 只有直接运行本文件时才执行 main；被 import 时不执行
    main()
