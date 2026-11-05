"""报警服务端：有人来调 trigger_alarm，就喊一句并回一个"已处理"。

服务的特点：一问一答。跟话题不同——
    话题：我喊出去就不管了，有没有人听、听没听懂，都不知道
    服务：我问一句，必须有人回一句，我还能拿到回复内容

本文件分三段：
    第1段  import + 定义类
    第2段  __init__ + on_request（核心只有 2 行）
    第3段  main
"""

# ============ 第 1 段 ============

import rclpy
from rclpy.node import Node
from sensor_interfaces.srv import TriggerAlarm


class AlarmServer(Node):

    # ============ 第 2 段 ============

    def __init__(self):
        super().__init__('alarm_server')

        # 建服务：名字 trigger_alarm，类型 TriggerAlarm。
        # 有人来请求时，ROS 会调用 self.on_request，并把它填好的 response 送回去。
        self.srv = self.create_service(TriggerAlarm, 'trigger_alarm', self.on_request)

        self.get_logger().info('报警服务已启动，等待调用...')

    def on_request(self, request, response):
        """request 是对方发来的内容，response 是我们要回给对方的内容。"""

        # request.message 就是节点C 填的那句"距离 0.20 米"
        self.get_logger().warn(f'[ALARM] 距离过近！对方说：{request.message}')

        # 往回复里填内容
        response.success = True
        response.response = '报警已处理'

        # ★ 必须 return response，对方才能收到回复。
        #   不 return 的话，调用方会一直等，最后超时。
        return response

    # ============ 第 3 段：标准启动流程 ============


def main(args=None):
    rclpy.init(args=args)
    node = AlarmServer()

    try:
        rclpy.spin(node)          # 卡在这里等服务请求
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
