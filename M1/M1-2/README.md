# M1-2 ｜ Launch 编排：一键启动两组实例

把 M1-1 的三个节点用一份 Python launch 文件启动，支持命名空间隔离、YAML 参数加载、
启动顺序控制和参数文件校验。

## 目录结构

```
M1-2/
├── src/
│   ├── sensor_interfaces/          # 接口包（复用 M1-1）
│   └── my_first_pkg/
│       ├── launch/
│       │   └── bringup.launch.py   # 一键启动脚本
│       └── my_first_pkg/           # 三个节点（复用 M1-1）
├── params_robot1.yaml              # robot1 参数（阈值 0.3）
├── params_robot2.yaml              # robot2 参数（阈值 0.5）
└── README.md
```

## 编译

```bash
cd ~/study/M1/M1-2
source /opt/ros/humble/setup.bash
colcon build
source install/setup.bash
```

## 一键启动

### 默认：同时启动两组（6 个节点）

```bash
ros2 launch my_first_pkg bringup.launch.py
```

### 只启动一组

```bash
ros2 launch my_first_pkg bringup.launch.py dual:=false
ros2 launch my_first_pkg bringup.launch.py dual:=false namespace:=my_robot
```

### 指定参数文件

```bash
ros2 launch my_first_pkg bringup.launch.py dual:=false params_file:=/path/to/my.yaml
```

## 验证

### 1. 六个节点同时在跑

```bash
ros2 node list
```

```
/robot1/node_a_sensor
/robot1/node_b_filter
/robot1/node_c_alarm
/robot2/node_a_sensor
/robot2/node_b_filter
/robot2/node_c_alarm
```

### 2. 同一份 launch、不同命名空间取不同参数

```bash
ros2 param get /robot1/node_c_alarm alarm_threshold     # Double value is: 0.3
ros2 param get /robot2/node_c_alarm alarm_threshold     # Double value is: 0.5
```

### 3. 两组话题互不干扰

```bash
ros2 topic list | grep sensor_data
```

```
/robot1/sensor_data
/robot2/sensor_data
```

`/robot1/processed_distance` 与 `/robot2/processed_distance` 同样隔离。

### 4. 参数文件不存在时给出可读提示

```bash
ros2 launch my_first_pkg bringup.launch.py params_file:=/nope.yaml
```

```
[启动失败] 参数文件不存在：/nope.yaml
           命名空间 robot1 需要该文件
           请检查 params_file 参数，或确认文件已生成
```

**没有 Python 栈回溯**，校验在 `OpaqueFunction` 内完成，失败即 `Shutdown`。

## Launch 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `dual` | `true` | true 同时起 robot1 + robot2；false 只起一组 |
| `namespace` | `robot1` | `dual=false` 时使用的命名空间 |
| `params_file` | 空 | YAML 路径，留空用默认文件 |
| `use_sim_time` | `false` | 是否使用仿真时间 |

## 参数文件格式

```yaml
/**/node_b_filter:
  ros__parameters:
    alpha: 0.3

/**/node_c_alarm:
  ros__parameters:
    alarm_threshold: 0.3
    service_timeout: 1.0
    cooldown: 2.0
```

**key 必须写成 `/**/节点名`**。节点带上命名空间后全名是 `/robot1/node_b_filter`，
用 `node_b_filter:` 这种相对 key **匹配不到**，参数不会生效。

## 实现要点

### 命名空间：GroupAction + PushRosNamespace

```python
GroupAction([
    PushRosNamespace(ns),
    node_a,
    node_b,
    ...
])
```

`PushRosNamespace` 作用于组内所有 action，节点名自动变成 `/robot1/node_a_sensor`。

**注意**：`PushRosNamespace` 在 `launch_ros.actions` 里，不在 `launch.actions`。写错模块会报
`ImportError: cannot import name 'PushRosNamespace'`。

### 启动顺序：节点C 在节点B 之后

```python
RegisterEventHandler(
    OnProcessStart(target_action=node_b, on_start=[node_c])
)
```

节点B 出现在进程列表里之后，才把节点C 加进 launch。

**踩过的坑**：事件回调里的 action **不继承** `GroupAction` 的命名空间，节点C 会跑到根命名空间下
（`/node_c_alarm`）。所以 `node_c` 需要显式写 `namespace=ns`。

### 错误处理：OpaqueFunction

参数文件路径只有在 launch 时才确定，普通 `LaunchDescription` 无法在加载阶段读取它。
`OpaqueFunction` 在 launch 时执行，可以先校验再返回节点列表：

```python
def _launch_setup(context):
    params_file = LaunchConfiguration('params_file').perform(context)
    if not os.path.isfile(params_file):
        return [LogInfo(msg='[启动失败] ...'), Shutdown(reason='...')]
    ...
```

## 已知限制

1. **报警服务端未包含在 launch 中。** 按题面要求 `ros2 node list` 应为 6 个节点，
   而服务端是第 4 个进程，因此没有放进 launch。节点C 会持续打印
   `[WARN] 报警服务超时`，这是预期行为。若要看完整报警链路，另开终端运行：
   ```bash
   ros2 run my_first_pkg alarm_server
   ```
   （注意：M1-2 的包内保留了 `alarm_server.py`，但未在 launch 中启动。）

2. 两组实例共用同一份节点代码，`alpha` 在两个 yaml 中都为 0.3，仅 `alarm_threshold` 不同。

3. `use_sim_time` 参数已声明并传给节点，但 M1-2 不涉及 bag 回放，实际未使用。

## AI 使用说明

launch 文件的结构由 AI 辅助生成，本人完成的验证：

- 确认 `ros2 node list` 输出 6 个带命名空间的节点
- 确认 `param get` 得到 0.3 / 0.5 两个不同值
- 确认话题按命名空间隔离
- 确认 `params_file:=/nope.yaml` 给出可读提示且无栈回溯
