"""报警服务端：有人调 trigger_alarm，就喊一句并返回"已处理"。

服务 vs 话题：
    话题：一方不停发，一方不停收，发的人不知道有没有人收到
    服务：我问一句，必须有人答一句，我还能拿到答案

三段结构：
    第1段  import + 定义类
    第2段  __init__ + on_request（真正干活的只有 5 行）
    第3段  main
"""

# ==================== 第 1 段 ====================

import rclpy                                        # ROS2 客户端库
from rclpy.node import Node                         # 节点父类
from sensor_interfaces.srv import TriggerAlarm      # 自定义服务类型


class AlarmServer(Node):

    # ==================== 第 2 段 ====================

    def __init__(self):
        super().__init__('alarm_server')            # 登记节点名，ros2 node list 显示 /alarm_server

        self.srv = self.create_service(             # 建服务（开通一条电话线）
            TriggerAlarm,                           # 服务类型
            'trigger_alarm',                        # 服务名（电话号码）
            self.on_request)                        # 有人打来就调这个函数

        self.get_logger().info('报警服务已启动，等待调用...')

    def on_request(self, request, response):        # 有人调用服务时自动执行
                                                    # request = 对方发来的内容；response = 要回给对方的内容
        self.get_logger().warn(f'[ALARM] 距离过近！对方说：{request.message}')
                                                    # request.message 就是节点C 填的那句话

        response.success = True                     # 填回复：成功
        response.response = '报警已处理'             # 填回复：一句话

        return response                             # ★ 必须 return，对方才收得到；不 return 调用方会超时

    # ==================== 第 3 段：标准启动流程 ====================


def main(args=None):
    rclpy.init(args=args)                           # ① 启动 ROS
    node = AlarmServer()                            # ② 造节点（执行 __init__，开通电话线）

    try:                                            # ③ 捕获 Ctrl+C
        rclpy.spin(node)                            # 卡在这里等服务请求
    except KeyboardInterrupt:                       # ④ 用户按 Ctrl+C
        pass
    finally:                                        # ⑤ 收尾
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
