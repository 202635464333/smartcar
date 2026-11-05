"""节点C：盯着距离，太近就调报警服务；服务不应答就报告超时。

链路位置：
    节点A --话题--> 节点B --话题--> 【节点C】 --服务--> alarm_server

五段结构：
    第1段  import + 定义类   准备工具
    第2段  __init__          登记：参数、订阅、服务客户端、超时定时器
    第3段  on_distance       每收到一个距离，过四道闸门
    第4段  check_timeout     每 0.1 秒检查"服务回话了吗"
    第5段  main              标准启动流程
"""

# ==================== 第 1 段：拿工具 ====================

import rclpy                                        # ROS2 客户端库
from rclpy.node import Node                         # 节点父类
from std_msgs.msg import Float32                    # 上游发来的是一个小数
from sensor_interfaces.srv import TriggerAlarm      # 自定义服务类型（srv，不是 msg）


class AlarmNode(Node):                              # 继承 Node

    # ==================== 第 2 段：登记 ====================

    def __init__(self):                             # 造节点时执行一次
        super().__init__('node_c_alarm')            # 登记节点名

        self.declare_parameter('alarm_threshold', 0.3)   # 报警阈值：低于多少米算太近
        self.declare_parameter('service_timeout', 1.0)   # 服务超时：等几秒算对方不理我
        self.declare_parameter('cooldown', 2.0)          # 冷却：两次报警至少隔几秒
                                                        # 三个都用 declare_parameter，才能被 ros2 param set 改

        self.last_alarm_time = None                 # 记"上次报警的时刻"；还没报过，所以是 None

        self.sub = self.create_subscription(        # 订阅滤波后的结果
            Float32,                                # 消息类型：一个小数
            'processed_distance',                   # 话题名（相对名）
            self.on_distance,                       # 收到就调这个函数
            10)                                     # 队列深度

        self.client = self.create_client(           # 建服务客户端（准备打电话）
            TriggerAlarm,                           # 服务类型
            'trigger_alarm')                        # 服务名；只是存了号码，还没拨

        self.future = None                          # 记"正在等谁回话"；None = 当前没在等
        self.send_time = None                        # 记"拨号时间"，用来算等了多久
        self.fired = 0                               # 报警次数，只为日志可读

        self.create_timer(0.1, self.check_timeout)  # ★ 单独一个定时器，每 0.1 秒查一次"回话了吗"
                                                    # 为什么不在 on_distance 里等？那会阻塞回调线程，节点卡死

        self.get_logger().info('节点C 启动：监听 processed_distance')

    # ==================== 第 3 段：过四道闸门 ====================

    def on_distance(self, msg):                     # 每收到一个距离执行一次
        threshold = self.get_parameter('alarm_threshold').value
                                                    # 现读阈值，改了参数立刻生效

        if msg.data >= threshold:                   # 闸门①：距离够远
            return                                  # 直接结束，不管

        if self.future is not None:                 # 闸门②：上一次请求还没回来
            return                                  # 不叠加，否则 10Hz 会打出 10 次/秒

        cooldown = self.get_parameter('cooldown').value      # 读冷却时间
        if self.last_alarm_time is not None:        # 便签上有字才比较（第一次是 None）
            gap = (self.get_clock().now() - self.last_alarm_time).nanoseconds / 1e9
                                                    # gap = 现在 - 上次 = 隔了多少秒
                                                    # .nanoseconds 是纳秒，除 1e9 换成秒
            if gap < cooldown:                      # 闸门③：不到冷却时间
                return                              # 这次不报

        self.fired += 1                             # 四道全过，开始报警
        self.get_logger().warn(                     # 打黄色警告
            f'距离过近 {msg.data:.3f} < {threshold}，调用报警服务（第 {self.fired} 次）')

        req = TriggerAlarm.Request()                # 造请求单
        req.message = f'距离 {msg.data:.2f} 米'      # 在请求单上写字

        self.future = self.client.call_async(req)   # ★ 异步调用：发出去立刻返回，不等结果
                                                    # 对比 call()：会原地死等，期间整个节点卡死

        self.send_time = self.get_clock().now()     # 记拨号时间，给超时检查用
        self.last_alarm_time = self.get_clock().now()   # 记报警时刻，给冷却用

    # ==================== 第 4 段：每 0.1 秒查一次 ====================

    def check_timeout(self):                        # 定时器每 0.1 秒调用一次
        if self.future is None:                     # 没在等任何人
            return                                  # 什么都不做

        if self.future.done():                      # 对方回话了
            resp = self.future.result()             # 取出回复内容
            self.get_logger().info(
                f'报警服务返回 success={resp.success}，{resp.response}')
                                                    # 打日志：成功与否、对方说了什么
            self.future = None                      # 清空，表示这次结束
            return

        waited = (self.get_clock().now() - self.send_time).nanoseconds / 1e9
                                                    # 还没回话：算已等了几秒

        timeout = self.get_parameter('service_timeout').value    # 允许等几秒
        if waited > timeout:                        # 超时了
            self.get_logger().warn(f'[WARN] 报警服务超时（已等 {waited:.1f} 秒）')
                                                    # ★ 打警告后放弃本次，继续运行（题目要求：不能死等、不能崩）
            self.future = None                      # 清空，好让下次能重新发

    # ==================== 第 5 段：标准启动流程 ====================


def main(args=None):
    rclpy.init(args=args)                           # ① 启动 ROS
    node = AlarmNode()                              # ② 造节点（执行 __init__）

    try:                                            # ③ 捕获 Ctrl+C
        rclpy.spin(node)                            # 卡在事件循环：来信调 on_distance，定时器调 check_timeout
    except KeyboardInterrupt:                       # ④ 用户按 Ctrl+C
        pass
    finally:                                        # ⑤ 收尾
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
