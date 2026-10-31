import rclpy
from rclpy.node import Node
from my_interfaces.msg import Target


class TargetSubscriber(Node):

    def __init__(self):
        super().__init__('target_subscriber')
        self.sub = self.create_subscription(Target, 'target', self.on_target, 10)
        self.last_stamp = None      # 上一帧的时间戳；第一帧时还没有，所以是 None
        self.accepted = 0           # 收下的帧数
        self.rejected = 0           # 丢掉的帧数
        self.get_logger().info('订阅者启动，监听 /target')

    def on_target(self, msg):
        # ① 算频率：这一帧和上一帧的时间差，取倒数
        hz = None
        if self.last_stamp is not None:
            dt = ((msg.stamp.sec - self.last_stamp.sec)
                  + (msg.stamp.nanosec - self.last_stamp.nanosec) * 1e-9)
            if dt > 0:                    # 防止时间戳乱序时除零
                hz = 1.0 / dt
        self.last_stamp = msg.stamp

        # ② 处理：置信度低于 0.5 就丢弃
        if msg.confidence < 0.5:
            self.rejected += 1
            self.get_logger().warn(
                f'丢弃低置信度 conf={msg.confidence:.2f} 累计丢弃={self.rejected}')
            return

        # ③ 收下的帧，每 10 帧打一次日志，避免刷屏
        self.accepted += 1
        if self.accepted % 10 == 1:
            hz_text = f'{hz:.1f}Hz' if hz else '首帧'
            self.get_logger().info(
                f'接受 {self.accepted} 帧 | x={msg.x:.2f} | 实测{hz_text} | 累计丢弃{self.rejected}')


def main(args=None):
    rclpy.init(args=args)
    node = TargetSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
