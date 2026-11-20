#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""图像处理与控制节点 —— 终端2 运行（已优化）

订阅:
    /camera/image_raw    640x480 mono8, 30Hz
发布:
    /perception/result   640x480 mono8, 30Hz
    /control/cmd         Twist, 20Hz

优化点（对照原版）：
    1. 删掉"放大到 1280×720"那一步
       —— 原版先把图放大到 1280×720 再处理、处理完再缩回 640×480，
          等于把计算量白放大 3 倍。题目明确允许改分辨率。
    2. 提亮和对比度改成 numpy 向量化
       —— 原版两个双重循环，1280×720 = 92 万像素 × 2 遍，
          单帧要 400ms 左右，这是输出只有 2.3Hz 的直接原因
    3. 订阅/发布 QoS 改成 BEST_EFFORT + depth=1
       —— 延迟的根因是"消息在队列里排队"，不是单帧算得慢。
          depth=30 + RELIABLE 意味着积压 30 帧 × 每帧 400ms = 12 秒的排队。
    4. 执行器从 SingleThreadedExecutor 改成 MultiThreadedExecutor
       —— 单线程时图像回调（几百毫秒）会把控制定时器的回调堵住，
          控制因此掉到 2.3Hz；多线程后两个节点的回调可以并行

保持不变：
    - 处理语义：转灰度 → 提亮 +20 → 对比度 (v-128)*3/2+128
    - 输出 640×480 mono8
    - ★ 输出 header.stamp 沿用输入（否则 ros2 topic delay 会假性归零）
"""

import time

import cv2
import numpy as np
import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import Twist
from rclpy.executors import MultiThreadedExecutor                  # ★ 单线程 → 多线程
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image

IMAGE_IN = "/camera/image_raw"
IMAGE_OUT = "/perception/result"
CMD_OUT = "/control/cmd"

IMAGE_WIDTH = 640
IMAGE_HEIGHT = 480
CONTROL_HZ = 20.0


def make_qos(depth=1):
    """图像链路 QoS。

    depth 是"最多缓存多少条还没处理的消息"。
    ★ 原版是 30 —— 积压 30 帧，每帧处理几百毫秒，延迟直接堆到秒级。
      这里设 1：只处理最新的那一帧，旧的直接丢。丢帧换来低延迟。
    """
    return QoSProfile(
        depth=depth,
        reliability=ReliabilityPolicy.BEST_EFFORT,                 # ★ 原版 RELIABLE → BEST_EFFORT
        history=HistoryPolicy.KEEP_LAST,
    )


def make_pub_qos():
    """输出话题的 QoS。

    与订阅端不同：订阅端要 BEST_EFFORT + depth=1（宁可丢帧也不排队），
    输出端用 RELIABLE + depth=5 —— 结果图丢了可惜，而且下游(如 ros2 topic hz、
    录制节点)通常用 RELIABLE 订阅，用 BEST_EFFORT 会让它们看到偏低的频率。
    """
    return QoSProfile(
        depth=5,
        reliability=ReliabilityPolicy.RELIABLE,
        history=HistoryPolicy.KEEP_LAST,
    )


class ImageProc(Node):
    def __init__(self):
        super().__init__("image_proc")
        self.sub = self.create_subscription(
            Image, IMAGE_IN, self.on_image, make_qos(depth=1)       # 订阅只留最新 1 帧
        )
        self.pub = self.create_publisher(Image, IMAGE_OUT, make_qos(depth=1))
        self.bridge = CvBridge()                                    # 消息转换器

        # 自计数：每 3 秒报一次真实处理/发布频率
        # 为什么不只用 ros2 topic hz？因为它自己也是订阅者，会与大图抢资源、还会丢帧
        self.count = 0
        self.t_start = time.monotonic()
        self.create_timer(3.0, self.report)

    def on_image(self, msg):
        # ---------- ① 拿图 ----------
        gray = self.bridge.imgmsg_to_cv2(msg, desired_encoding="mono8")
                                                                     # 输入是 mono8，直接拿到 uint8 数组

        # ---------- ② 提亮 +20 （★ 向量化，等价于原版的双重循环）----------
        bright = np.clip(gray.astype(np.int16) + 20, 0, 255).astype(np.uint8)
                                                                     # 加 20 后截断到 0~255，等价于原版的 if>255: 255

        # ---------- ③ 对比度 (v-128)*3/2+128 （★ 向量化）----------
        v = bright.astype(np.int16)                                  # 转有符号，避免负数溢出
        contrast = np.clip((v - 128) * 3 // 2 + 128, 0, 255).astype(np.uint8)
                                                                     # // 对负数是向下取整，与原版 Python // 一致
                                                                     # 原版还夹了 if<0: 0 / if>255: 255，clip 一并做掉

        # ---------- ④ 发布 ----------
        out = self.bridge.cv2_to_imgmsg(contrast, encoding="mono8")
        out.header.stamp = msg.header.stamp                          # ★ 必须沿用输入时间戳，否则延迟假性归零
        out.header.frame_id = msg.header.frame_id
        self.pub.publish(out)
        self.count += 1                                             # 发布计数

    def report(self):
        elapsed = time.monotonic() - self.t_start
        if elapsed <= 0:
            return
        self.get_logger().info(
            "[PROC] 已发布 %d 帧, 平均 %.2f Hz (目标 30.0 Hz)"
            % (self.count, self.count / elapsed))


class ControlLoop(Node):
    def __init__(self):
        super().__init__("control_loop")
        self.pub = self.create_publisher(Twist, CMD_OUT, make_qos(depth=1))
        # 同样留 4% 余量：create_timer 的实际周期 = 设定值 + 回调开销，直设 1/20 会跑成 19.9Hz
        self.timer = self.create_timer(1.0 / (CONTROL_HZ * 1.04), self.on_timer)

    def on_timer(self):
        cmd = Twist()
        cmd.linear.x = 0.10                                          # 前进速度
        cmd.angular.z = 0.05                                         # 转向角速度
        self.pub.publish(cmd)


def main():
    rclpy.init()
    nodes = [ImageProc(), ControlLoop()]                             # 两个节点
    executor = MultiThreadedExecutor(num_threads=2)                  # ★ 多线程：图像回调不再堵住控制回调
    for node in nodes:
        executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        for node in nodes:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
