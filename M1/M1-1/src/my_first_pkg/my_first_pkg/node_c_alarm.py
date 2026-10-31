import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from sensor_interfaces.srv import TriggerAlarm


class AlarmNode(Node):
    """节点C：距离低于阈值时调用报警服务，处理超时"""

    def __init__(self):
        super().__init__('node_c_alarm')

        self.declare_parameter('alarm_threshold', 0.3)
        self.declare_parameter('service_timeout', 1.0)
        self.declare_parameter('cooldown', 2.0)
        self.last_alarm_time = None

        self.sub = self.create_subscription(
            Float32, 'processed_distance', self.on_distance, 10)

        # 服务客户端：跟 alarm_server 对接
        self.client = self.create_client(TriggerAlarm, 'trigger_alarm')

        self.future = None       # 正在等待的请求
        self.send_time = None
        self.fired = 0

        # 单独一个定时器查超时，不能在回调里阻塞
        self.create_timer(0.1, self.check_timeout)

        self.get_logger().info('节点C 启动：监听 processed_distance')

    def on_distance(self, msg):
        threshold = self.get_parameter('alarm_threshold').value

        if msg.data >= threshold:
            return
        if self.future is not None:      # 上一次还没结束，跳过
            return

        # 冷却：距上次报警不足 cooldown 秒就跳过
        cooldown = self.get_parameter('cooldown').value
        if self.last_alarm_time is not None:
            gap = (self.get_clock().now() - self.last_alarm_time).nanoseconds / 1e9
            if gap < cooldown:
                return

        self.fired += 1
        self.get_logger().warn(
            f'距离过近 {msg.data:.3f} < {threshold}，调用报警服务（第 {self.fired} 次）')

        req = TriggerAlarm.Request()
        req.message = f'距离 {msg.data:.2f} 米'
        self.future = self.client.call_async(req)    # 不阻塞
        self.send_time = self.get_clock().now()
        self.last_alarm_time = self.get_clock().now()

    def check_timeout(self):
        if self.future is None:
            return

        if self.future.done():
            resp = self.future.result()
            self.get_logger().info(
                f'报警服务返回 success={resp.success}，{resp.response}')
            self.future = None
            return

        waited = (self.get_clock().now() - self.send_time).nanoseconds / 1e9
        timeout = self.get_parameter('service_timeout').value
        if waited > timeout:
            self.get_logger().warn(f'[WARN] 报警服务超时（已等 {waited:.1f} 秒）')
            self.future = None


def main(args=None):
    rclpy.init(args=args)
    node = AlarmNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
