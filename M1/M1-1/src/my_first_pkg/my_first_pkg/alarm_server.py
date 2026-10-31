import rclpy
from rclpy.node import Node
from sensor_interfaces.srv import TriggerAlarm


class AlarmServer(Node):

    def __init__(self):
        super().__init__('alarm_server')
        # 建一个服务：名字 trigger_alarm，类型 TriggerAlarm，收到请求就调 on_request
        self.srv = self.create_service(TriggerAlarm, 'trigger_alarm', self.on_request)
        self.get_logger().info('报警服务已启动，等待调用...')

    def on_request(self, request, response):
        # request 是对方发来的，response 是要返回给对方的
        self.get_logger().warn(f'[ALARM] 距离过近！对方说：{request.message}')
        response.success = True
        response.response = '报警已处理'
        return response          # 必须把 response 返回去，对方才收得到


def main(args=None):
    rclpy.init(args=args)
    node = AlarmServer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
