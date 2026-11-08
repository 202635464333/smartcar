# M1-3 ｜ 时间与坐标：把激光点投影到相机图像

一块摄像头、一块激光雷达，装在不同位置、不同频率、时间戳还不同源。
本节点把激光测到的点画到相机拍的照片上，并**按距离上色**（近红远蓝）。

## 目录结构

```
M1-3/
├── src/projection_pkg/projection_pkg/projection_node.py   # 投影节点（本题代码）
├── make_bag.py                  # 数据生成器（社团提供）
├── extrinsics.yaml              # 外参/内参真值（生成数据时写出，唯一真值来源）
├── sample_bag/                  # 生成的 rosbag（未入库，现场重新生成）
├── projection_01.png            # 投影效果图 ×3
├── projection_02.png
├── projection_03.png
└── README.md
```

## 生成数据

```bash
python3 make_bag.py --frames 60          # 约 6 秒，143 MB
```

会同时写出 `extrinsics.yaml`（激光/相机的安装位置 + 相机内参）。

## 编译与运行

```bash
cd ~/study/M1/M1-3
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash

# 终端1：跑投影节点。★ 回放 bag 必须 use_sim_time:=true
ros2 run projection_pkg projection_node --ros-args \
  -p use_sim_time:=true \
  -p extrinsics_file:=extrinsics.yaml \
  -p output_dir:=. \
  -p max_images:=3 \
  -p slop:=0.06

# 终端2：回放数据（必须带 --clock 才会发布 /clock）
ros2 bag play sample_bag --clock --rate 0.5
```

跑完后当前目录会出现 `projection_01.png` ~ `projection_03.png`。

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `extrinsics_file` | `extrinsics.yaml` | 外参/内参文件路径 |
| `output_dir` | `.` | 效果图输出目录 |
| `max_images` | 3 | 最多存几张 |
| `slop` | 0.05 | 近似同步允许的时间差（秒） |
| `queue_size` | 50 | 同步队列深度 |
| `log_every` | 10 | 每配几对打一次统计（做实验时设 1） |
| `use_sim_time` | false | 回放 bag 时必须 true |

## 实现说明

### 1. TF 树（数值全部读自 extrinsics.yaml）

```
map → odom → base_link → laser_link
                       ↘ camera_link
```

- `map → odom → base_link`：题目要求存在，未给数值，用单位变换
- `base_link → laser_link`：平移 `[0.15, 0.0, 0.20]`
- `base_link → camera_link`：平移 `[0.10, 0.0, 0.30]`，rpy 全 0

用 `StaticTransformBroadcaster` 发一次即可（发布到 `/tf_static`）。

**★ 代码里没有任何写死的安装数值**，全部从 yaml 读。现场换一组外参重新生成数据，
代码不用改就能对上——写死的实现会当场错得很明显。

### 2. 时间同步

雷达 10 Hz、相机 27 Hz，时间戳**不同源**（各有独立时钟 + 抖动），
用 `TimeSynchronizer`（精确同步）一帧都配不上，必须用
`ApproximateTimeSynchronizer`。

`queue_size` 设 50：相机 27Hz、雷达 10Hz，队列小了早期帧会滚出丢掉。

### 3. slop 取值实验（数据支撑）

固定 60 帧雷达数据，逐个 slop 值跑一遍，记录配对数与时间差中位数：

| slop | 配对数 | 时间差中位数 |
| :--: | :--: | :--: |
| 20 ms | 15 | 5.2 ms |
| 40 ms | 19 | 17.4 ms |
| 60 ms | 19~22 | 20~24 ms |
| 100 ms | 30 | 35.2 ms |
| 150 ms | 30 | 32.5 ms |

**读法：**

- `20ms`：只配上 15 对，**一半以上的雷达帧被丢掉**，但配对时间差只有 5ms
- `100ms` 以上：配对数到 30 就**不再增长**（饱和），时间差升到 35ms
- `60ms`：能配上 20 对左右，时间差 20ms 上下

**为什么默认选 60ms**：配对数已达到饱和值的三分之二，继续加大 slop 只换来更差的时间
对齐，不换来更多帧。20ms 太严会把有效数据丢掉一半。

> 注意 `ApproximateTimeSynchronizer` 是**一对一贪心匹配**，不是"每个雷达帧各找最近的相机帧"。
> 相机比雷达快 2.7 倍，多余的相机帧会被丢弃，所以**实际配对时间差会比"理论最近距离"大**。

### 4. 点云投影

每个激光点 `(range, angle)` → 激光坐标系 `(r·cosθ, r·sinθ, 0)`：

1. 用 `lookup_transform('camera_link', 'laser_link', stamp)` 变到相机坐标系
2. **相机坐标系 → 光学坐标系**（`z 前 / x 右 / y 下`）：
   ```
   X_opt = -Y_link
   Y_opt = -Z_link
   Z_opt =  X_link
   ```
   ★ 这一步是"投影上下颠倒或左右镜像"的根源，符号写反图像就翻
3. 投影公式：
   ```
   u = fx · X_opt / Z_opt + cx
   v = fy · Y_opt / Z_opt + cy
   ```
4. 只保留 `Z_opt > 0`（相机前方的点），并裁剪到图像范围内
5. 按欧氏距离归一化上色：近处 (0,0,255) 红，远处 (255,0,0) 蓝

**结果校验**：相机比激光高 0.1 米，所以激光点应该落在**地平线略下方**；
越近的点越低（v 越大）。三张效果图都符合，颜色由中心红向外围蓝渐变。

### 5. use_sim_time

- 回放 bag 时 `ros2 bag play` 必须带 `--clock`，否则不发布 `/clock`
- 节点必须 `use_sim_time:=true`，否则用系统真实时间，与数据时间戳对不上，
  TF 查询会报 `LookupException`（时间戳在缓存里找不到）

**对比实验结论**：

| use_sim_time | 现象 |
|---|---|
| `false`（回放 bag 时） | 节点时钟停在真实时间，`/clock` 不生效；`lookup_transform` 用数据时间戳查 TF 时找不到对应时刻，报错配不上，一张图都存不出来 |
| `true` | 节点时钟跟随 `/clock`，与数据时间戳一致，TF 查询成功，正常出图 |

## 接口契约

| 名称 | 类型 | 方向 |
|---|---|---|
| `/scan` | `sensor_msgs/LaserScan` | 输入（bag） |
| `/camera/image_raw` | `sensor_msgs/Image` | 输入（bag） |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | 输入（bag，本节点未直接使用，内参从 yaml 读） |
| `/projection/debug_image` | `sensor_msgs/Image`（`bgr8`） | **输出** |
| `/tf_static` | `tf2_msgs/TFMessage` | 静态 TF |

坐标系：`map` / `odom` / `base_link` / `laser_link` / `camera_link`

## 已知限制

1. **效果图是横线状**：2D 激光在一个水平面上，所以投影出来必然是一条横向窄带，
   不是"点云覆盖画面"。这是数据本身决定的，不是 bug。
2. `/camera/camera_info` 话题没有订阅：内参直接从 `extrinsics.yaml` 读，
   题目要求该文件为唯一真值来源。
3. `use_sim_time` 的对比只有文字结论，录屏未附（本地无录屏工具）。
4. 配对率最高到 30/60 对，未找出全部丢帧原因，推测与 `ApproximateTimeSynchronizer`
   的贪心匹配策略有关（相机帧数约为雷达 2.7 倍，多余相机帧被丢弃）。

## AI 使用说明

代码由 AI 辅助生成，本人在真机上的验证：

- `ros2 node list` / `ros2 topic list` 确认话题正确
- 三张效果图中激光点均落在地平线下方，近红远蓝，符合"相机高于激光平面"的物理预期
- slop 5 档实验亲手跑出上表数据
- 切换 `use_sim_time` 观察过失败与成功的差异
