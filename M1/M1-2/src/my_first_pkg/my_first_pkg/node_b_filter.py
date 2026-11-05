"""节点B：把节点A 发来的距离做一阶低通滤波，再转发出去。

它在整条链路里的位置：
    节点A --/sensor_data--> 【节点B】 --/processed_distance--> 节点C

本文件分四段：
    第1段  import + 定义类      —— 准备工具、声明"我要造一个节点"
    第2段  __init__             —— 节点建好时登记：听谁、说给谁、记住什么
    第3段  on_data              —— 每收到一条消息就跑一次（核心逻辑）
    第4段  main                 —— 标准启动流程，四个节点都一样
"""

# ============ 第 1 段：拿工具、定义类 ============

import rclpy                          # ROS2 的 Python 客户端库，所有节点都要它
from rclpy.node import Node           # Node 是父类，我们的节点继承它才能用 ROS 的功能
from std_msgs.msg import Float32      # 标准消息：只装一个小数（我们要发出去的滤波结果）
from sensor_interfaces.msg import SensorData   # 自定义消息：从传感器收进来的数据（4 个字段）


class FilterNode(Node):
    """继承 Node，等于"我造一个新型号的节点"。

    括号里的 Node 就是继承，意思是：FilterNode 自动拥有 Node 的所有能力
    （create_publisher / create_subscription / declare_parameter 这些都是 Node 给的）。
    """

    # ============ 第 2 段：节点建好时，把该登记的登记好 ============

    def __init__(self):
        # 把节点名交给父类 Node，让它去 ROS 里注册。
        # 名字会出现在 ros2 node list 里，显示为 /node_b_filter
        # 这一句必须在最前面——先注册，才能往下用。
        super().__init__('node_b_filter')

        # 声明一个参数 alpha，默认 0.3。
        # 不写这一句，外面的 ros2 param set 会报
        # "Parameter 'alpha' has not been declared"，改不了。
        self.declare_parameter('alpha', 0.3)

        # 订阅：听 'sensor_data' 这个话题，消息类型 SensorData，
        # 每收到一条就调用 self.on_data，最后一个 10 是队列深度（最多缓存 10 条）
        self.sub = self.create_subscription(
            SensorData, 'sensor_data', self.on_data, 10)

        # 发布：往 'processed_distance' 这个话题发 Float32 类型
        #   收的是 4 个字段的 SensorData，发的是 1 个数——因为下游只关心距离
        self.pub = self.create_publisher(Float32, 'processed_distance', 10)

        # 记住"上一次的滤波结果"。
        # 第一帧时还没有上一次，所以先设成 None（Python 里表示"还没有值"）
        self.y = None

        # 计数器，只为了"每 10 帧打一次日志"，避免刷屏
        self.count = 0

        self.get_logger().info('节点B 启动：一阶低通，alpha 默认 0.3')

    # ============ 第 3 段：每收到一条消息，就跑一次（核心） ============

    def on_data(self, msg):
        """msg 就是节点A 发来的那条 SensorData，有 distance / unit / stamp / status 四个字段。"""

        # --- ① 先检查数据能不能用 ---
        # status：0=正常，1=超出量程，2=传感器错误
        if msg.status != 0:
            # 打一条警告，让人知道丢了什么数据
            self.get_logger().warn(
                f'丢弃无效数据 status={msg.status} distance={msg.distance:.2f}')
            # return 直接结束本函数，下面的滤波和发布都不执行
            # 注意：这个判断必须放在滤波之前！否则坏数据会污染 self.y，
            #      之后好几帧的滤波结果都会跟着歪。
            return

        # --- ② 读参数 ---
        # 每次进来都重新读一遍，而不是启动时读一次存起来。
        # 这样外部 ros2 param set 改了参数，下一帧立刻生效，不用重启。
        alpha = self.get_parameter('alpha').value

        # --- ③ 一阶低通滤波：y = alpha * x + (1 - alpha) * y_prev ---
        # 意思：这次的结果 = α 倍的新数据 + (1-α) 倍的上次结果
        #   α 小（如 0.1）→ 新数据权重低 → 曲线平滑、跟随慢
        #   α 大（如 0.9）→ 几乎直接用新数据 → 跳动大、但有滞后小
        if self.y is None:
            # 第一帧没有"上一次"，没法套公式，直接拿原值当第一次的滤波结果
            self.y = msg.distance
        else:
            # 从第二帧开始才能算
            self.y = alpha * msg.distance + (1 - alpha) * self.y

        # 发出去。Float32(data=...) 是构造一条只装小数的消息。
        # 加 float() 是为了确保类型是 Python 的 float，避免 numpy 类型报错
        self.pub.publish(Float32(data=float(self.y)))

        # 每 10 帧打一次日志（帧数用 10 取余 == 0 判断）
        self.count += 1
        if self.count % 10 == 0:
            self.get_logger().info(f'滤波后={self.y:.3f}（alpha={alpha}）')

    # ============ 第 4 段：标准启动流程（四个节点完全一样） ============


def main(args=None):
    rclpy.init(args=args)          # ① 启动 ROS 客户端库
    node = FilterNode()            # ② 造节点（这一行会执行上面的 __init__）

    try:
        rclpy.spin(node)           # ③ 进入事件循环，卡在这里等消息
                                   #    每来一条 sensor_data，spin 就替我们调一次 on_data
    except KeyboardInterrupt:      # ④ 你按 Ctrl+C 时，别让它吐一堆红色报错
        pass
    finally:
        node.destroy_node()        # ⑤ 先销毁节点
        rclpy.shutdown()           #    再关闭客户端库


if __name__ == '__main__':
    main()
