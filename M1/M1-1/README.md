# M1-1 三节点链路 + 动态配参

虚拟超声波测距链路：**传感器 → 滤波 → 报警**，用到话题、服务、参数、自定义接口四种机制。

## 目录结构

```
M1-1/
├── src/
│   ├── sensor_interfaces/          # 接口包（ament_cmake）
│   │   ├── msg/SensorData.msg      # 传感器数据
│   │   ├── srv/TriggerAlarm.srv    # 报警服务
│   │   ├── CMakeLists.txt
│   │   └── package.xml
│   └── my_first_pkg/               # 节点包（ament_python）
│       └── my_first_pkg/
│           ├── node_a_sensor.py    # 节点A 传感器
│           ├── node_b_filter.py    # 节点B 滤波
│           ├── node_c_alarm.py     # 节点C 报警
│           └── alarm_server.py     # 报警服务端
└── README.md
```

## 编译

```bash
cd ~/study/M1/M1-1
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## 运行

需要 4 个终端。**每个终端都要先执行这两条**：

```bash
source /opt/ros/humble/setup.bash
source ~/study/M1/M1-1/install/setup.bash
```

| 终端 | 命令 | 作用 |
|---|---|---|
| 1 | `ros2 run my_first_pkg alarm_server` | 报警服务端 |
| 2 | `ros2 run my_first_pkg node_a_sensor` | 传感器，10Hz 发布 |
| 3 | `ros2 run my_first_pkg node_b_filter` | 滤波，发布处理结果 |
| 4 | `ros2 run my_first_pkg node_c_alarm` | 报警判断 |

顺序不限。等 10 秒左右，距离摆到 0.3 米以下时，终端4 会开始报警。

## 验证方法

### 1. 节点都在

```bash
ros2 node list
```

应看到 4 个：

```
/alarm_server
/node_a_sensor
/node_b_filter
/node_c_alarm
```

### 2. 频率正确

```bash
ros2 topic hz /processed_distance
```

应约 **10 Hz**（节点A 的发布频率）。

### 3. 参数可动态修改（重点）

```bash
ros2 param get /node_b_filter alpha      # 0.3
ros2 param set /node_b_filter alpha 0.9
```

改完观察终端3 的「滤波后」数值：

| alpha | 现象 |
|---|---|
| 0.3 | 输出平滑，跟随原始值较慢 |
| 0.9 | 输出跳动明显变大，几乎不滤波 |

**不需要重启节点，下一帧就生效。**

### 4. 服务可调用

```bash
ros2 service call /trigger_alarm sensor_interfaces/srv/TriggerAlarm "{message: '手动测试'}"
```

返回 `success=True`，终端1 打印 `[ALARM] 距离过近！`。

### 5. 超时能正确处理

把终端1（服务端）按 `Ctrl+C` 杀掉，再观察终端4：

```
[WARN] [node_c_alarm]: [WARN] 报警服务超时（已等 1.1 秒）
```

程序**不阻塞、不崩溃**，继续运行。

## 参数表

| 节点 | 参数 | 默认值 | 说明 |
|---|---|---|---|
| node_b_filter | `alpha` | 0.3 | 一阶低通滤波系数 |
| node_c_alarm | `alarm_threshold` | 0.3 | 报警阈值（米） |
| node_c_alarm | `service_timeout` | 1.0 | 服务超时（秒） |
| node_c_alarm | `cooldown` | 2.0 | 报警冷却（秒） |

## 接口

| 名称 | 类型 | 方向 |
|---|---|---|
| `/sensor_data` | `sensor_interfaces/msg/SensorData` | A → B |
| `/processed_distance` | `std_msgs/msg/Float32` | B → C |
| `/trigger_alarm` | `sensor_interfaces/srv/TriggerAlarm` | C 调用 |

## 设计说明

### 一阶低通滤波

```python
y = alpha * x + (1 - alpha) * y_prev
```

`x` 是本次收到的距离，`y_prev` 是上次的滤波结果。**alpha 越小越平滑**（新数据权重低），alpha 越大越接近原始值。第一帧没有 `y_prev`，直接取原值。

### 无效数据放在滤波之前

`status != 0` 的数据直接 return，**不进入滤波**。如果先滤波再判断，无效值会污染 `y`，之后几帧的滤波结果都被带偏。

### 服务超时用异步实现

`call()` 会阻塞当前回调线程，导致整个节点卡死，连超时检测的机会都没有。因此用 `call_async()` 拿 future，另开 0.1 秒定时器轮询 `future.done()`，超过 `service_timeout` 就放弃本次请求。

### 报警冷却

传感器 10Hz，距离持续低于阈值时每帧都会触发一次服务调用（实测 1 秒触发 10 次，累计 400+ 次）。加入 `cooldown` 参数后，距上次报警不足 2 秒直接跳过，实测间隔 ≥ 2.1 秒。

冷却做成参数而非写死，是为了现场可调。

### 话题名使用相对名

节点里写 `'sensor_data'` 而不是 `'/sensor_data'`。相对名才能被 namespace 隔离（M1-2 需要 `/robot1/...` 与 `/robot2/...` 两组并行）；绝对名会绕过命名空间。

## 已知限制

1. 传感器数据是**模拟值**（正弦摆动 0.15~1.15 米），不是真实超声波读数。
2. 报警服务端是**独立进程**（`alarm_server`），不是嵌在节点C 内部。
3. **服务端未启动**与**服务端响应超时**在代码里表现相同（都是 future 不完成），依靠 `service_timeout` 统一处理，没有区分这两种情况。
4. 未做多传感器并发测试，链路按单路设计。

## AI 使用说明

本题的代码骨架由 AI 辅助生成，本人逐行阅读并做了以下验证：

- 注释掉 `declare_parameter`，确认 `ros2 param set` 报 `Parameter 'alpha' has not been declared`
- 修改 `alpha` 从 0.3 到 0.9，观察输出平滑度变化
- 杀掉服务端，确认打印超时警告且程序不崩溃
- 加入冷却逻辑后重跑，确认报警间隔从每秒多次变为 ≥2 秒
