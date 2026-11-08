"""M1-3 投影节点：把激光雷达的点画到相机图像上。

四件事（对应题目四个要求）：
    1. 建 TF 树：map → odom → base_link → laser_link / camera_link（数值从 extrinsics.yaml 读，不写死）
    2. 时间同步：雷达 10Hz、相机 27Hz 时间戳不同源，用 ApproximateTimeSynchronizer 配最近的一对
    3. 投影：激光点 → 相机坐标系 → 像素坐标，按距离上色（近红远蓝）
    4. use_sim_time 由命令行/参数控制（回放 bag 时必须 true）

数据流：
    /scan + /camera/image_raw ──同步──> 本节点 ──> /projection/debug_image
                                          └──> 存 png（最多 max_images 张）
"""

import os

import cv2
import numpy as np
import rclpy
import yaml
from cv_bridge import CvBridge
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, LaserScan
from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
from geometry_msgs.msg import TransformStamped


class ProjectionNode(Node):

    def __init__(self):
        super().__init__('projection_node')

        # ---------- 参数 ----------
        self.declare_parameter('extrinsics_file', 'extrinsics.yaml')  # 外参/内参真值文件
        self.declare_parameter('output_dir', '.')                     # 效果图输出目录
        self.declare_parameter('max_images', 3)                       # 最多存几张
        self.declare_parameter('slop', 0.05)                          # 允许的时间差（秒）
        self.declare_parameter('queue_size', 50)                      # 同步队列深度
        self.declare_parameter('log_every', 10)                       # 每配几对报一次数（做 slop 实验时设 1）

        extr_file = self.get_parameter('extrinsics_file').value
        self.output_dir = self.get_parameter('output_dir').value
        self.max_images = int(self.get_parameter('max_images').value)
        slop = float(self.get_parameter('slop').value)
        queue_size = int(self.get_parameter('queue_size').value)
        self.log_every = int(self.get_parameter('log_every').value)

        # ---------- 读外参/内参（唯一真值来源，绝不写死）----------
        self.extr = self.load_extrinsics(extr_file)
        self.fx = self.extr['camera_intrinsics']['fx']
        self.fy = self.extr['camera_intrinsics']['fy']
        self.cx = self.extr['camera_intrinsics']['cx']
        self.cy = self.extr['camera_intrinsics']['cy']

        # ---------- TF：发静态变换 ----------
        self.tf_static = StaticTransformBroadcaster(self)
        self.publish_static_tf()

        # TF 查询需要 buffer + listener
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ---------- 时间同步 ----------
        # 用 Subscriber（不是 create_subscription），这样才能喂给同步器
        self.sub_scan = Subscriber(self, LaserScan, '/scan', qos_profile=qos_profile_sensor_data)
        self.sub_img = Subscriber(self, Image, '/camera/image_raw', qos_profile=qos_profile_sensor_data)

        self.sync = ApproximateTimeSynchronizer(
            [self.sub_scan, self.sub_img],
            queue_size=queue_size,   # 队列要够大，否则早期帧会滚出
            slop=slop,               # 允许的最大时间差
        )
        self.sync.registerCallback(self.on_pair)

        # ---------- 发布 + 存图 ----------
        self.pub = self.create_publisher(Image, '/projection/debug_image', 10)
        self.bridge = CvBridge()
        self.saved = 0               # 已存几张
        self.pairs = 0               # 已配上的帧数（给 slop 实验用）
        self.diffs = []              # 每对的|时间差|，用来算中位数

        os.makedirs(self.output_dir, exist_ok=True)
        self.get_logger().info(
            f'投影节点启动：fx={self.fx} fy={self.fy} cx={self.cx} cy={self.cy}，slop={slop*1000:.0f}ms')

    # ==================== 工具：读 yaml ====================

    def load_extrinsics(self, path):
        if not os.path.isfile(path):
            raise RuntimeError(f'外参文件不存在：{path}')
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    # ==================== 第 1 件事：发静态 TF ====================

    def make_tf(self, parent, child, xyz, rpy=(0.0, 0.0, 0.0)):
        """造一条 TF 消息：parent → child，平移 xyz，旋转 rpy（这里只用 yaw=0 的情况）"""
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = parent
        t.child_frame_id = child
        t.transform.translation.x = float(xyz[0])
        t.transform.translation.y = float(xyz[1])
        t.transform.translation.z = float(xyz[2])

        # rpy → 四元数（只处理 roll/pitch/yaw 三个角，标准公式）
        roll, pitch, yaw = [float(v) for v in rpy]
        cy_, sy_ = np.cos(yaw * 0.5), np.sin(yaw * 0.5)
        cp, sp = np.cos(pitch * 0.5), np.sin(pitch * 0.5)
        cr, sr = np.cos(roll * 0.5), np.sin(roll * 0.5)
        t.transform.rotation.x = sr * cp * cy_ - cr * sp * sy_
        t.transform.rotation.y = cr * sp * cy_ + sr * cp * sy_
        t.transform.rotation.z = cr * cp * sy_ - sr * sp * cy_
        t.transform.rotation.w = cr * cp * cy_ + sr * sp * sy_
        return t

    def publish_static_tf(self):
        """按题目的树结构发 4 条：
              map → odom → base_link → laser_link
                                    ↘ camera_link
           数值全部来自 extrinsics.yaml，现场换一组数据也能对。
        """
        laser = self.extr['laser_link']
        cam = self.extr['camera_link']

        zero = (0.0, 0.0, 0.0)
        transforms = [
            self.make_tf('map', 'odom', zero),                 # 题目要求有这一层，数值未给，用单位变换
            self.make_tf('odom', 'base_link', zero),           # 同上
            self.make_tf(laser['parent'], 'laser_link', laser['xyz']),
            self.make_tf(cam['parent'], 'camera_link', cam['xyz'], cam.get('rpy', zero)),
        ]
        self.tf_static.sendTransform(transforms)
        self.get_logger().info(f'已发布 {len(transforms)} 条静态 TF')

    # ==================== 第 2、3 件事：同步 + 投影 ====================

    def on_pair(self, scan, image):
        """同步成功的一对（同一时刻附近的雷达帧 + 图像帧）会进到这里。"""
        self.pairs += 1

        # 记录这一对的时间差，供 slop 实验统计
        dt = abs((scan.header.stamp.sec + scan.header.stamp.nanosec * 1e-9)
                 - (image.header.stamp.sec + image.header.stamp.nanosec * 1e-9))
        self.diffs.append(dt)

        # 图像消息 → OpenCV 格式（bgr8 方便 cv2 画图）
        try:
            frame = self.bridge.imgmsg_to_cv2(image, desired_encoding='bgr8')
        except Exception as e:
            self.get_logger().error(f'图像转换失败：{e}')
            return

        # 查 TF：把点从 laser_link 变到 camera_link
        try:
            tf_l2c = self.tf_buffer.lookup_transform(
                'camera_link',            # 目标坐标系
                scan.header.frame_id,     # 源坐标系（laser_link）
                scan.header.stamp)        # 用数据自己的时间戳（不是 now）
        except Exception as e:
            self.get_logger().warn(f'查 TF 失败（可能还没收到）：{e}')
            return

        # 提取旋转矩阵 + 平移向量
        q = tf_l2c.transform.rotation
        t = tf_l2c.transform.translation
        R = self.quat_to_matrix(q.x, q.y, q.z, q.w)
        T = np.array([t.x, t.y, t.z])

        # 生成激光点（2D，z=0）
        angles = scan.angle_min + np.arange(len(scan.ranges)) * scan.angle_increment
        ranges = np.array(scan.ranges, dtype=np.float32)

        # 过滤无效值：inf / nan / 超出量程的都不要
        valid = np.isfinite(ranges) & (ranges >= scan.range_min) & (ranges <= scan.range_max)
        angles = angles[valid]
        ranges = ranges[valid]
        if ranges.size == 0:
            return

        # 激光坐标系下的点：(r·cosθ, r·sinθ, 0)
        pts_l = np.stack([
            ranges * np.cos(angles),
            ranges * np.sin(angles),
            np.zeros_like(ranges),
        ], axis=1)

        # 变到相机坐标系（REP-103：x 前、y 左、z 上）
        pts_c = (R @ pts_l.T).T + T

        # 相机坐标系 → 光学坐标系（z 前、x 右、y 下）
        # 这一步是"上下颠倒/左右镜像"的根源，符号写反投影就会翻
        X = -pts_c[:, 1]
        Y = -pts_c[:, 2]
        Z = pts_c[:, 0]

        # 只保留相机前方的点
        front = Z > 1e-3
        X, Y, Z = X[front], Y[front], Z[front]
        if Z.size == 0:
            return

        # 投影公式
        u = (self.fx * X / Z + self.cx).astype(np.int32)
        v = (self.fy * Y / Z + self.cy).astype(np.int32)

        h, w = frame.shape[:2]
        inside = (u >= 0) & (u < w) & (v >= 0) & (v < h)

        # 按距离上色：近红远蓝
        r = np.sqrt(X ** 2 + Y ** 2 + Z ** 2)
        r_norm = (r - r.min()) / max(r.max() - r.min(), 1e-6)   # 0~1
        for ui, vi, ri in zip(u[inside], v[inside], r_norm[inside]):
            color = (int(255 * (1 - ri)), 0, int(255 * ri))     # BGR：(255,0,0)=蓝，(0,0,255)=红
            cv2.circle(frame, (int(ui), int(vi)), 2, color, -1)

        # 发出去（转回 ROS Image）
        out = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
        out.header = image.header            # ★ 沿用输入的 header，ros2 topic delay 才测得准
        self.pub.publish(out)

        # 存图（最多 max_images 张）
        if self.saved < self.max_images:
            self.saved += 1
            path = os.path.join(self.output_dir, f'projection_{self.saved:02d}.png')
            cv2.imwrite(path, frame)
            self.get_logger().info(f'已保存 {path}（第 {self.pairs} 对，时间差 {dt*1000:.1f}ms）')

        # 每 10 对报一次统计（给 slop 实验看配对率）
        if self.pairs % self.log_every == 0:
            med = float(np.median(self.diffs)) * 1000
            self.get_logger().info(f'已配对 {self.pairs} 对，时间差中位数 {med:.1f}ms')

    @staticmethod
    def quat_to_matrix(x, y, z, w):
        """四元数 → 3x3 旋转矩阵"""
        return np.array([
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])


def main(args=None):
    rclpy.init(args=args)
    node = ProjectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
