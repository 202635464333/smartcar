"""M1-3 投影节点：把激光雷达的点画到相机图像上。

四件事（对应题目四个要求）：
    1. 建 TF 树：map → odom → base_link → laser_link / camera_link（数值从 extrinsics.yaml 读，绝不写死）
    2. 时间同步：雷达 10Hz、相机 27Hz 时间戳不同源，用 ApproximateTimeSynchronizer 配最近的一对
    3. 投影：激光点 → 相机坐标系 → 光学坐标系 → 像素坐标，按距离上色（近红远蓝）
    4. use_sim_time 由参数控制（回放 bag 时必须 true）

数据流：
    /scan + /camera/image_raw ──同步──> 本节点 ──> /projection/debug_image
                                          └──> 存 png（最多 max_images 张）

七段结构：
    第1段  import                          拿工具
    第2段  __init__                        读参数、读 yaml、发 TF、建同步器、建发布者
    第3段  load_extrinsics / make_tf / publish_static_tf     第1件事：TF
    第4段  on_pair                         第2、3件事：同步回调 + 投影（核心）
    第5段  quat_to_matrix                  工具：四元数转矩阵
    第6段  main                            标准启动流程
"""

# ==================== 第 1 段：拿工具 ====================

import os                                                       # 路径拼接、判断文件存在

import cv2                                                      # OpenCV：画点、存图
import numpy as np                                              # 数值计算：数组、三角函数、矩阵乘法
import rclpy                                                    # ROS2 客户端库
import yaml                                                     # 读 extrinsics.yaml
from cv_bridge import CvBridge                                  # ROS 图像消息 ↔ OpenCV 图像 的转换器
from message_filters import (                                   # 时间同步工具
    ApproximateTimeSynchronizer,                                # 近似同步：允许两个时间戳差一点点
    Subscriber,                                                 # 可喂给同步器的订阅者（注意不是 create_subscription）
)
from rclpy.node import Node                                     # 节点父类
from rclpy.qos import qos_profile_sensor_data                    # 传感器常用 QoS（best_effort，深度 5）
from sensor_msgs.msg import Image, LaserScan                    # 两个输入消息类型
from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
                                                                # Buffer=存变换的地方；StaticTransformBroadcaster=发静态TF；TransformListener=收听TF
from geometry_msgs.msg import TransformStamped                  # 一条 TF 消息的类型


class ProjectionNode(Node):                                     # 继承 Node

    # ==================== 第 2 段：初始化 ====================

    def __init__(self):
        super().__init__('projection_node')                     # 登记节点名

        # ---------- 声明参数（都可在命令行用 -p 名:=值 覆盖）----------
        self.declare_parameter('extrinsics_file', 'extrinsics.yaml')  # 外参/内参真值文件
        self.declare_parameter('output_dir', '.')                     # 效果图输出目录
        self.declare_parameter('max_images', 3)                       # 最多存几张
        self.declare_parameter('slop', 0.05)                          # 近似同步允许的最大时间差（秒）
        self.declare_parameter('queue_size', 50)                      # 同步队列深度
        self.declare_parameter('log_every', 10)                       # 每配几对报一次数（做 slop 实验时设 1）

        # ---------- 把参数读出来 ----------
        extr_file = self.get_parameter('extrinsics_file').value       # yaml 路径
        self.output_dir = self.get_parameter('output_dir').value      # 存图目录
        self.max_images = int(self.get_parameter('max_images').value) # 最多存几张
        slop = float(self.get_parameter('slop').value)                # 时间差上限（秒）
        queue_size = int(self.get_parameter('queue_size').value)      # 队列深度
        self.log_every = int(self.get_parameter('log_every').value)   # 日志频率

        # ---------- 读外参/内参（唯一真值来源）----------
        self.extr = self.load_extrinsics(extr_file)                   # 整个 yaml 存成字典
        self.fx = self.extr['camera_intrinsics']['fx']                # 焦距 x
        self.fy = self.extr['camera_intrinsics']['fy']                # 焦距 y
        self.cx = self.extr['camera_intrinsics']['cx']                # 图像中心 x（640/2）
        self.cy = self.extr['camera_intrinsics']['cy']                # 图像中心 y（480/2）
                                                                      # ★ 四个数都不写死，现场换内参也能对

        # ---------- TF：发静态变换 + 建查询缓存 ----------
        self.tf_static = StaticTransformBroadcaster(self)             # 静态 TF 广播器（发一次，永久有效）
        self.publish_static_tf()                                      # 立刻发出 4 条

        self.tf_buffer = Buffer()                                     # 存收到的 TF，供查询
        self.tf_listener = TransformListener(self.tf_buffer, self)    # 开始收听 /tf 和 /tf_static

        # ---------- 时间同步 ----------
        self.sub_scan = Subscriber(                                   # 雷达订阅（用 message_filters 的 Subscriber）
            self, LaserScan, '/scan',                                 # 节点、类型、话题
            qos_profile=qos_profile_sensor_data)                      # 传感器 QoS
        self.sub_img = Subscriber(                                    # 图像订阅
            self, Image, '/camera/image_raw',
            qos_profile=qos_profile_sensor_data)

        self.sync = ApproximateTimeSynchronizer(                      # ★ 近似同步器（不是精确同步）
            [self.sub_scan, self.sub_img],                            # 要同步的几路
            queue_size=queue_size,                                    # 队列深度：小了早期帧会滚出丢掉
            slop=slop,                                                # 允许的最大时间差
        )
        self.sync.registerCallback(self.on_pair)                      # 配上对之后调 on_pair

        # ---------- 发布 + 存图 ----------
        self.pub = self.create_publisher(Image, '/projection/debug_image', 10)
                                                                      # 输出话题：带投影的图
        self.bridge = CvBridge()                                      # 消息 ↔ OpenCV 的转换器
        self.saved = 0                                                # 已存几张图
        self.pairs = 0                                                # 已配上的帧数（给 slop 实验用）
        self.diffs = []                                               # 每一对的时间差，用来算中位数

        os.makedirs(self.output_dir, exist_ok=True)                   # 建输出目录（已存在也不报错）
        self.get_logger().info(
            f'投影节点启动：fx={self.fx} fy={self.fy} cx={self.cx} cy={self.cy}，slop={slop*1000:.0f}ms')

    # ==================== 第 3 段：第 1 件事 —— 静态 TF ====================

    def load_extrinsics(self, path):
        """读 yaml，返回一个字典（嵌套的）。"""
        if not os.path.isfile(path):                                  # 文件不存在就直接报错退出
            raise RuntimeError(f'外参文件不存在：{path}')
        with open(path, 'r', encoding='utf-8') as f:                  # 打开文件
            return yaml.safe_load(f)                                  # 解析成字典

    def make_tf(self, parent, child, xyz, rpy=(0.0, 0.0, 0.0)):
        """造一条 TF：从一个坐标系到另一个坐标系的平移 + 旋转。"""
        t = TransformStamped()                                        # 造一条空 TF 消息
        t.header.stamp = self.get_clock().now().to_msg()              # 时间戳
        t.header.frame_id = parent                                    # 父坐标系（从哪来）
        t.child_frame_id = child                                      # 子坐标系（到哪去）
        t.transform.translation.x = float(xyz[0])                     # 平移 x（左右）
        t.transform.translation.y = float(xyz[1])                     # 平移 y（前后）
        t.transform.translation.z = float(xyz[2])                     # 平移 z（上下）

        roll, pitch, yaw = [float(v) for v in rpy]                    # 三个旋转角（本数据全是 0）
        cy_, sy_ = np.cos(yaw * 0.5), np.sin(yaw * 0.5)               # 下面是 rpy → 四元数的标准公式
        cp, sp = np.cos(pitch * 0.5), np.sin(pitch * 0.5)             # 拆成三个半角的余弦/正弦
        cr, sr = np.cos(roll * 0.5), np.sin(roll * 0.5)
        t.transform.rotation.x = sr * cp * cy_ - cr * sp * sy_        # 四元数 x
        t.transform.rotation.y = cr * sp * cy_ + sr * cp * sy_        # 四元数 y
        t.transform.rotation.z = cr * cp * sy_ - sr * sp * cy_        # 四元数 z
        t.transform.rotation.w = cr * cp * cy_ + sr * sp * sy_        # 四元数 w
        return t                                                      # 返回这条 TF

    def publish_static_tf(self):
        """按题目要求发 4 条静态 TF，数值全部来自 extrinsics.yaml。

            map → odom → base_link → laser_link
                                  ↘ camera_link
        """
        laser = self.extr['laser_link']                               # 激光那份配置
        cam = self.extr['camera_link']                                # 相机那份配置

        zero = (0.0, 0.0, 0.0)                                        # 单位变换用的零值
        transforms = [
            self.make_tf('map', 'odom', zero),                        # 题目要求有这一层，未给数值 → 单位变换
            self.make_tf('odom', 'base_link', zero),                   # 同上
            self.make_tf(laser['parent'], 'laser_link', laser['xyz']),  # base_link → laser_link，用 yaml 里的 xyz
            self.make_tf(cam['parent'], 'camera_link', cam['xyz'], cam.get('rpy', zero)),
                                                                      # base_link → camera_link，xyz + rpy
        ]
        self.tf_static.sendTransform(transforms)                      # 一次性全部发出
        self.get_logger().info(f'已发布 {len(transforms)} 条静态 TF')

    # ==================== 第 4 段：第 2、3 件事 —— 同步回调 + 投影（核心） ====================

    def on_pair(self, scan, image):
        """同步成功的一对（时间上最接近的雷达帧 + 图像帧）会进到这里。"""
        self.pairs += 1                                               # 配对数 +1

        dt = abs((scan.header.stamp.sec + scan.header.stamp.nanosec * 1e-9)
                 - (image.header.stamp.sec + image.header.stamp.nanosec * 1e-9))
                                                                      # 算这一对的时间差（秒）：sec + nanosec×1e-9
        self.diffs.append(dt)                                         # 记下来，最后算中位数

        try:                                                          # 消息 → OpenCV 图像
            frame = self.bridge.imgmsg_to_cv2(image, desired_encoding='bgr8')
        except Exception as e:                                        # 编码不对等异常
            self.get_logger().error(f'图像转换失败：{e}')
            return                                                    # 这张跳过

        try:                                                          # 查 TF：把点从雷达坐标系变到相机坐标系
            tf_l2c = self.tf_buffer.lookup_transform(
                'camera_link',                                        # ★ 第一个参数是"目标"坐标系
                scan.header.frame_id,                                 # ★ 第二个是"源"坐标系（顺序写反会得到逆变换）
                scan.header.stamp)                                    # 用数据自己的时间戳，不是 now
        except Exception as e:                                        # TF 还没到 / use_sim_time 没开
            self.get_logger().warn(f'查 TF 失败（可能还没收到）：{e}')
            return

        q = tf_l2c.transform.rotation                                 # 提取旋转（四元数）
        t = tf_l2c.transform.translation                              # 提取平移
        R = self.quat_to_matrix(q.x, q.y, q.z, q.w)                   # 四元数 → 3×3 矩阵
        T = np.array([t.x, t.y, t.z])                                 # 平移向量

        angles = scan.angle_min + np.arange(len(scan.ranges)) * scan.angle_increment
                                                                      # 每个激光点对应的角度：起始角 + 序号×角增量
        ranges = np.array(scan.ranges, dtype=np.float32)               # 每个点的距离

        valid = np.isfinite(ranges) & (ranges >= scan.range_min) & (ranges <= scan.range_max)
                                                                      # 过滤：nan/inf 丢掉，超出量程的也丢掉
        angles = angles[valid]                                        # 只留有效的角度
        ranges = ranges[valid]                                        # 只留有效的距离
        if ranges.size == 0:                                          # 全被过滤掉了
            return

        pts_l = np.stack([                                            # 激光坐标系下的点（2D，z 恒为 0）
            ranges * np.cos(angles),                                  # x = r·cosθ
            ranges * np.sin(angles),                                  # y = r·sinθ
            np.zeros_like(ranges),                                    # z = 0
        ], axis=1)                                                    # 拼成 N×3 的数组

        pts_c = (R @ pts_l.T).T + T                                   # 乘旋转矩阵再加平移 → 变到相机坐标系
                                                                      # (R @ pts_l.T) 得到 3×N，转置回 N×3

        X = -pts_c[:, 1]                                              # ★ 相机坐标系 → 光学坐标系
        Y = -pts_c[:, 2]                                              #   x_opt = -y_link
        Z = pts_c[:, 0]                                               #   y_opt = -z_link
                                                                      #   z_opt =  x_link
                                                                      # ★ 这三个符号是"投影上下颠倒/左右镜像"的根源，写反图就翻

        front = Z > 1e-3                                              # 只保留相机前方（深度为正）的点
        X, Y, Z = X[front], Y[front], Z[front]                        # 过滤
        if Z.size == 0:                                               # 全在相机后面
            return

        u = (self.fx * X / Z + self.cx).astype(np.int32)              # 投影公式：u = fx·X/Z + cx
        v = (self.fy * Y / Z + self.cy).astype(np.int32)              # 投影公式：v = fy·Y/Z + cy

        h, w = frame.shape[:2]                                        # 图像高、宽
        inside = (u >= 0) & (u < w) & (v >= 0) & (v < h)              # 落在画面内的点

        r = np.sqrt(X ** 2 + Y ** 2 + Z ** 2)                         # 每个点到相机的直线距离
        r_norm = (r - r.min()) / max(r.max() - r.min(), 1e-6)         # 归一化到 0~1（分母加 1e-6 防除零）
        for ui, vi, ri in zip(u[inside], v[inside], r_norm[inside]):  # 逐点画
            color = (int(255 * (1 - ri)), 0, int(255 * ri))           # BGR：近处 (0,0,255) 红，远处 (255,0,0) 蓝
            cv2.circle(frame, (int(ui), int(vi)), 2, color, -1)       # 画半径 2 的实心圆

        out = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')       # 转回 ROS Image 消息
        out.header = image.header                                     # ★ 沿用输入的 header（时间戳不变）
                                                                      #   重新打时间戳会让 ros2 topic delay 假性归零
        self.pub.publish(out)                                         # 发出去

        if self.saved < self.max_images:                              # 还没存够张数
            self.saved += 1                                           # 计数 +1
            path = os.path.join(self.output_dir, f'projection_{self.saved:02d}.png')
                                                                      # 拼路径：projection_01.png
            cv2.imwrite(path, frame)                                  # 存图
            self.get_logger().info(f'已保存 {path}（第 {self.pairs} 对，时间差 {dt*1000:.1f}ms）')

        if self.pairs % self.log_every == 0:                          # 每 N 对报一次统计
            med = float(np.median(self.diffs)) * 1000                 # 时间差中位数（毫秒）
            self.get_logger().info(f'已配对 {self.pairs} 对，时间差中位数 {med:.1f}ms')

    # ==================== 第 5 段：工具函数 ====================

    @staticmethod                                                     # 静态方法：不需要 self
    def quat_to_matrix(x, y, z, w):
        """四元数 → 3×3 旋转矩阵（ROS 里旋转都用四元数存，算的时候要换成矩阵）。"""
        return np.array([                                             # 标准公式，照抄即可
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ])

    # ==================== 第 6 段：标准启动 ====================


def main(args=None):
    rclpy.init(args=args)                                             # ① 启动 ROS
    node = ProjectionNode()                                           # ② 造节点（执行 __init__）

    try:                                                              # ③ 捕获 Ctrl+C
        rclpy.spin(node)                                              # 卡在事件循环里等同步好的数据
    except KeyboardInterrupt:                                         # ④ 用户按 Ctrl+C
        pass
    finally:                                                          # ⑤ 收尾
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
