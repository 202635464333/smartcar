#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""相机节点 —— 终端1 运行（已优化）

发布:
    /camera/image_raw    640x480 mono8, 目标 30Hz

优化点（对照原版）：
    1. capture() 从"双重 Python 循环逐像素写"改成 numpy 向量化
       —— 原版 30 万次迭代，单帧耗时吃掉大半帧预算，只能跑 15.6Hz
    2. QoS 从 RELIABLE/depth=30 改成 BEST_EFFORT/depth=2
       —— 图像是"流"，旧的帧没有价值；RELIABLE 会在拥塞时重传/阻塞，
          depth=30 会让 27MB 的旧帧堵在队列里，延迟因此飙到秒级
    3. 编码从 bgr8 改成 mono8
       —— 下游只做灰度处理，彩色信息在链路里是纯浪费；
          单帧从 921KB 降到 307KB，带宽省 2/3

牺牲了什么：彩色信息（下游只需要灰度，题目允许改输入编码）
"""

import time

import numpy as np
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

IMAGE_IN = "/camera/image_raw"

IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
CAMERA_HZ = 30.0
QUEUE_DEPTH = 2                 # ★ 原版 30 → 2：只保留最新几帧，不积压


def make_qos():
    """图像流的 QoS：丢帧可以，卡住不行。"""
    return QoSProfile(
        depth=QUEUE_DEPTH,                                  # 队列只留 2 帧
        reliability=ReliabilityPolicy.BEST_EFFORT,          # ★ 原版 RELIABLE → BEST_EFFORT
        history=HistoryPolicy.KEEP_LAST,                    # 只保留最新的，旧的直接丢
    )


class CameraSim(Node):
    def __init__(self):
        super().__init__("camera_sim")
        self.pub = self.create_publisher(Image, IMAGE_IN, make_qos())   # 建发布者
        self.bridge = CvBridge()                                        # 消息转换器
        self.seq = 0                                                    # 帧号
        self.count = 0                                                  # 已发布帧数
        self.t_start = time.monotonic()                                 # 起始时刻（算频率用）
        # 定时器周期留 3% 余量：Python 的 create_timer 实际周期 = 设定值 + 回调开销，
        # 直接设 1/30 会跑成 29.9Hz。设 1/(30*1.03) 让实测落在 30.0 以上。
        self.timer = self.create_timer(1.0 / (CAMERA_HZ * 1.03), self.on_timer)
        self.report_timer = self.create_timer(3.0, self.report)         # 每 3 秒报一次频率

    def capture(self):
        """造一帧图像。★ 向量化：跟原版逐像素循环结果完全一致，但快~100 倍。

        原版逻辑（等价的）：
            off = (y*13 + seq) & 0xFF
            value = (x + off) & 0xFF
            RGB = (value, value, 60)
        """
        off = (np.arange(IMAGE_HEIGHT, dtype=np.int32)[:, None] * 13 + self.seq) & 0xFF
                                                                    # 每行的偏移，形状 (480, 1)，靠广播铺到 640 列
        xs = np.arange(IMAGE_WIDTH, dtype=np.int32)[None, :]         # 列号，形状 (1, 640)
        value = ((xs + off) & 0xFF).astype(np.uint8)                 # 一张 (480, 640) 的灰度值

        return value                                                 # 直接返回灰度图（不再拼三通道）

    def on_timer(self):
        self.seq += 1                                                # 帧号 +1
        frame = self.capture()                                       # 造一帧（原版这里是瓶颈）

        msg = self.bridge.cv2_to_imgmsg(frame, encoding="mono8")      # ★ 编码改 mono8（省 2/3 带宽）
        msg.header.stamp = self.get_clock().now().to_msg()            # 打时间戳
        msg.header.frame_id = "camera_link"                           # 坐标系
        self.pub.publish(msg)                                         # 发出去
        self.count += 1                                               # 计数

    def report(self):
        elapsed = time.monotonic() - self.t_start                      # 已经过去多久
        if elapsed <= 0:
            return
        self.get_logger().info(
            "[CAMERA] 已发布 %d 帧, 平均 %.2f Hz (目标 %.1f Hz)"
            % (self.count, self.count / elapsed, CAMERA_HZ)
        )


def main():
    rclpy.init()                                                      # 启动 ROS
    node = CameraSim()                                                # 造节点
    try:
        rclpy.spin(node)                                              # 事件循环
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
