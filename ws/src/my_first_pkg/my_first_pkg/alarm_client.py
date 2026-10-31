import rclpy
from rclpy.node import Node
from sensor_interfaces.srv import TriggerAlarm


class AlarmClient(Node):

    def __init__(self):
        super().__init__('alarm_client')

        # 超时时间做成参数，默认 1 秒
        self.declare_parameter('service_timeout', 1.0)

        self.client = self.create_client(TriggerAlarm, 'trigger_alarm')

        self.future = None       # 还没回来的"请求"，None 表示当前没有在等
        self.send_time = None    # 什么时候发出去的

        # 两个定时器，各管一件事
        self.create_timer(2.0, self.send_request)   # 每 2 秒发起一次调用
        self.create_timer(0.1, self.check_result)   # 每 0.1 秒看一次回来了没有

    def send_request(self):
        if self.future is not None:
            return                      # 上一次还没结束，跳过

        req = TriggerAlarm.Request()
        req.message = '距离过近，请求报警'

        # call_async：发出去立刻返回，不在这里等结果
        self.future = self.client.call_async(req)
        self.send_time = self.get_clock().now()
        self.get_logger().info('已发出报警请求，等待应答...')

    def check_result(self):
        if self.future is None:
            return

        if self.future.done():
            # 对方回话了
            resp = self.future.result()
            self.get_logger().info(f'收到应答：success={resp.success}，{resp.response}')
            self.future = None
            return

        # 还没回话，看看等了多久
        waited = (self.get_clock().now() - self.send_time).nanoseconds / 1e9
        timeout = self.get_parameter('service_timeout').value
        if waited > timeout:
            self.get_logger().warn(f'[WARN] 报警服务超时（已等 {waited:.1f} 秒）')
            self.future = None          # 放弃这次，下次重新发


def main(args=None):
    rclpy.init(args=args)
    node = AlarmClient()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
