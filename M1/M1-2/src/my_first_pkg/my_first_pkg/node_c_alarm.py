"""节点C：盯着滤波后的距离，太近就调报警服务；服务不理我就报告超时。

在链路里的位置：
    节点A --/sensor_data--> 节点B --/processed_distance--> 【节点C】 --调用服务--> alarm_server

本文件分五段：
    第1段  import + 定义类   —— 准备工具
    第2段  __init__          —— 登记：订阅、参数、服务客户端、超时定时器
    第3段  on_distance       —— 每收到一个距离，过四道闸门，决定报不报警
    第4段  check_timeout     —— 每 0.1 秒看一眼"服务回话了吗"
    第5段  main              —— 标准启动流程
"""

# ============ 第 1 段 ============

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32                    # 上游发来的是一个小数
from sensor_interfaces.srv import TriggerAlarm      # 自己定义的服务类型


class AlarmNode(Node):

    # ============ 第 2 段：登记 ============

    def __init__(self):
        super().__init__('node_c_alarm')

        # --- 三个参数，都能被 ros2 param set 现场修改 ---
        self.declare_parameter('alarm_threshold', 0.3)   # 低于多少米算"太近"
        self.declare_parameter('service_timeout', 1.0)   # 等多久算"服务超时"
        self.declare_parameter('cooldown', 2.0)          # 两次报警至少隔多久

        # 记住"上一次报警的时刻"，用来算冷却。
        # 还没报过警，所以是 None（空）。
        self.last_alarm_time = None

        # 订阅滤波后的结果
        self.sub = self.create_subscription(
            Float32, 'processed_distance', self.on_distance, 10)

        # 建服务客户端：我要去调 'trigger_alarm' 这个服务，类型是 TriggerAlarm。
        # create_client 只是"准备好联系方式"，真正打电话是下面的 call_async
        self.client = self.create_client(TriggerAlarm, 'trigger_alarm')

        # future = "正在等待的请求"。None 表示当前没有在等任何人回话。
        self.future = None
        # 记下这次请求是什么时候发出去的，用来算等了多久
        self.send_time = None
        # 报警次数计数，只为了日志好看
        self.fired = 0

        # ★ 单独开一个 0.1 秒的定时器，专门检查"回话了吗"。
        #   为什么不能在上面的 on_distance 里等？因为那会阻塞回调线程，
        #   整个节点会卡死，连这个定时器都跑不起来。
        self.create_timer(0.1, self.check_timeout)

        self.get_logger().info('节点C 启动：监听 processed_distance')

    # ============ 第 3 段：收到一个距离，过四道闸门 ============

    def on_distance(self, msg):
        # 先把阈值读出来（每次现读，改了参数立刻生效）
        threshold = self.get_parameter('alarm_threshold').value

        # --- 闸门①：距离够远，不关我事 ---
        # msg.data 是上游发来的滤波结果
        if msg.data >= threshold:
            return

        # --- 闸门②：上一次的请求还没回来，不叠加 ---
        # 防止 10Hz 的数据每帧都去发请求，把服务端打爆
        if self.future is not None:
            return

        # --- 闸门③：冷却时间没到，不重复报 ---
        # 看表：现在距上次报警多久了？
        cooldown = self.get_parameter('cooldown').value
        if self.last_alarm_time is not None:      # 第一次报警时是 None，跳过这层判断
            # 现在时刻 - 上次时刻 = 间隔；.nanoseconds 是纳秒，除以 1e9 换成秒
            gap = (self.get_clock().now() - self.last_alarm_time).nanoseconds / 1e9
            if gap < cooldown:
                return                            # 还不够 2 秒，这次不报

        # --- 四道全过，可以报警了 ---
        self.fired += 1
        self.get_logger().warn(
            f'距离过近 {msg.data:.3f} < {threshold}，调用报警服务（第 {self.fired} 次）')

        # 造一个请求
        req = TriggerAlarm.Request()
        req.message = f'距离 {msg.data:.2f} 米'

        # ★ call_async：发出去立刻返回，不在这里等结果。
        #   对比 call()：那会原地死等，等的时候整个节点什么都干不了。
        self.future = self.client.call_async(req)

        # 记下两个时间：一个给超时检查用，一个给冷却用
        self.send_time = self.get_clock().now()
        self.last_alarm_time = self.get_clock().now()

    # ============ 第 4 段：每 0.1 秒检查一次"回话了吗" ============

    def check_timeout(self):
        # 没在等任何人，什么都不做
        if self.future is None:
            return

        # 对方回话了
        if self.future.done():
            resp = self.future.result()          # 取出对方返回的内容
            self.get_logger().info(
                f'报警服务返回 success={resp.success}，{resp.response}')
            self.future = None                    # 清空，表示这次结束了
            return

        # 还没回话：看看等了多久，超时了没
        waited = (self.get_clock().now() - self.send_time).nanoseconds / 1e9
        timeout = self.get_parameter('service_timeout').value
        if waited > timeout:
            # ★ 超时了就放弃这次请求，打印警告，然后继续跑。
            #   这是题目要求的：不能死等、不能崩溃。
            self.get_logger().warn(f'[WARN] 报警服务超时（已等 {waited:.1f} 秒）')
            self.future = None

    # ============ 第 5 段：标准启动流程 ============


def main(args=None):
    rclpy.init(args=args)
    node = AlarmNode()

    try:
        rclpy.spin(node)      # 事件循环：收到消息叫 on_distance，定时器到点叫 check_timeout
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
