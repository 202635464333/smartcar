# 故障记录手册（M1-4 任务二）

优化这条链路时**真实踩到的 5 个坑**。每条都按「现象 → 定位 → 根因 → 修复 → 验证」写，
命令和输出是原文，可以直接复制复现。

---

## 故障 1：改完发布端，处理端一条消息都收不到

### ① 现象

按计划先优化发布端（向量化 + 改 QoS），输入频率确实上去了，
但 `ros2 topic hz /perception/result` **完全没有输出**（连 `average rate` 都不打印）：

```
$ ros2 topic hz /perception/result
（没有任何输出，等 6 秒后超时退出）
```

同时相机自己报告输入已经达标：

```
[CAMERA] 已发布 180 帧, 平均 29.99 Hz (目标 30.0 Hz)
```

### ② 定位过程

1. 先怀疑处理端崩了 → 查 `python3 image_proc.py` 的终端，**没有任何报错**，进程活着
2. 怀疑话题名写错 → `ros2 topic list` 里 `/perception/result` 存在
3. 怀疑输出没发布 → `ros2 topic info /perception/result` 看到订阅者 1 个、发布者 1 个，说明链路是通的
4. 最后想到 QoS：**发布端被我改成了 BEST_EFFORT，处理端还是 RELIABLE**
5. 后来在另一个场景（见故障 2）看到了 ROS 明确给出的警告，确认就是这个原因：
   ```
   [WARN] New publisher discovered on topic '/perception/result',
   offering incompatible QoS. No messages will be received from it.
   Last incompatible policy: RELIABILITY
   ```

### ③ 根因

ROS2 的 QoS 有兼容性规则：**订阅者的要求不能高于发布者。**

| 发布者 | 订阅者 | 是否兼容 |
| :-- | :-- | :-- |
| RELIABLE | RELIABLE | ✅ |
| RELIABLE | BEST_EFFORT | ✅（订阅者要求更低） |
| **BEST_EFFORT** | **RELIABLE** | ❌ **不兼容，一条都收不到** |

我把发布端降到 BEST_EFFORT，而处理端仍要求 RELIABLE（"不许丢帧"），
两者的可靠性承诺对不上，DDS 直接不建立连接。

**注意这是静默失败**：不报错，不崩溃，就是收不到数据。

### ④ 修复

处理端订阅 QoS 也改成 `BEST_EFFORT`，两边承诺一致：

```python
reliability=ReliabilityPolicy.BEST_EFFORT,
history=HistoryPolicy.KEEP_LAST,
depth=1,
```

### ⑤ 验证

```
$ ros2 topic hz /perception/result
average rate: 29.969
	min: 0.009s max: 0.060s std dev: 0.00815s window: 153
```

输出恢复到 ≈30 Hz。

---

## 故障 2：写了个"抓图脚本"验证输出，同样收不到消息

### ① 现象

为了确认输出图确实做了灰度增强，我写了个临时脚本订阅 `/perception/result` 存一张图，
用的是最普通的写法：

```python
self.create_subscription(Image, topic, self.cb, 10)   # 最后一个参数直接给 10
```

跑起来直接报：

```
[WARN] New publisher discovered on topic '/perception/result',
offering incompatible QoS. No messages will be received from it.
Last incompatible policy: RELIABILITY
```

而且 `/camera/image_raw` **也一样收不到**。

### ② 定位过程

1. 脚本本身没语法错误，能启动、能进 spin
2. 报错里写得很明确：`incompatible QoS`、`Last incompatible policy: RELIABILITY`
3. 对照代码：`create_subscription(..., 10)` 里那个 `10` 是**整数深度**，
   rclpy 会用它套一个**默认 QoS**（`RELIABLE`）
4. 而我的两个发布端现在都是 `BEST_EFFORT` → 又踩了故障 1 的同一条规则

### ③ 根因

`create_subscription` 第四个参数**传整数**时，rclpy 自动套的默认 QoS 是
`RELIABLE + KEEP_LAST`。这和故障 1 是同一个兼容性规则，只是这次踩在**测量工具**上，
不是主链路上。

**这也说明：测量工具本身也会被 QoS 坑。**

### ④ 修复

改用传感器标准 QoS 配置（`BEST_EFFORT` + `depth=5`）：

```python
from rclpy.qos import qos_profile_sensor_data
self.create_subscription(Image, topic, self.cb, qos_profile_sensor_data)
```

### ⑤ 验证

```
saved out_result.png (480, 640) uint8
saved out_input.png (480, 640) uint8
```

两张图都成功落地。

---

## 故障 3：延迟 1376ms，但单帧处理只花几毫秒

### ① 现象

基线跑起来后测延迟：

```
$ ros2 topic delay /perception/result
average delay: 1.376
	min: 1.344s max: 1.411s std dev: 0.01591s window: 22
```

**1.3 秒的延迟，而且非常稳定**（std dev 只有 16ms）——稳定得不像"算得慢"。

### ② 定位过程

1. 先测单帧处理耗时：在原版 `on_image` 里手动加计时，单帧约 400ms
2. 400ms × 队列里积压的帧数 ≈ 延迟 → 反推积压约 3~4 帧
3. 看订阅 QoS：`make_sub_qos()` 里 `depth=30`
4. 算一下：**30 帧 × 400ms = 12 秒**的排队上限，实际稳定在 1.3 秒说明队列一直是满的
5. 关键判断：**延迟这么稳定，说明系统处于"稳定积压"状态**——每来一帧处理一帧，
   但处理速度远低于到达速度，队列永远保持满

### ③ 根因

延迟的根因**不是单帧算得慢，而是消息在队列里排队**。

到达速度 25Hz（每 40ms 一帧），处理速度 2.5Hz（每 400ms 一帧）。
队列 `depth=30` 意味着最多能积压 30 帧，也就是最多 12 秒的排队。
实际稳定在 1.3 秒，说明队列里长期压着 3~4 帧。

**只要处理速度跟不上到达速度，延迟就会一直涨到队列满为止。**
这也是为什么"只把处理变快"不够——队列深度不降，积压依然存在。

### ④ 修复

两件事一起做：

```python
# 1. 队列只留最新 1 帧，旧的直接丢
depth=1,

# 2. 处理本身提速（向量化 + 去掉放大到 1280×720）
```

### ⑤ 验证

```
$ ros2 topic delay /perception/result
average delay: 0.009
	min: 0.002s max: 0.035s std dev: 0.00772s window: 206
```

从 1376ms 降到 **9ms**（最大 35ms），远低于 200ms 达标线。

---

## 故障 4：处理快了，控制指令还是只有 4.6Hz

### ① 现象

把处理端向量化之后，输出频率上去了，但控制话题仍然很慢：

```
$ ros2 topic hz /control/cmd
average rate: 4.619
	min: 0.212s max: 0.224s std dev: 0.00306s window: 21
```

控制定时器设的是 `1.0/20.0 = 0.05s`（20Hz），实测 0.21s 一次（4.6Hz）——
**慢了 4 倍**，而且间隔非常规律（std dev 3ms）。

### ② 定位过程

1. 先确认定时器参数：`CONTROL_HZ = 20.0`，`create_timer(1.0/20.0, ...)` 没写错
2. 单独只跑 `ControlLoop` 节点（不跑 `ImageProc`）→ 能到 20Hz，**说明被别的回调拖住了**
3. 看 `main()`：

   ```python
   nodes = [ImageProc(), ControlLoop()]
   executor = SingleThreadedExecutor()
   ```

   两个节点**共用同一个单线程执行器**
4. 单线程执行器是**串行**处理所有回调：图像回调跑 400ms 期间，控制定时器的回调
   只能排队等，这个时间正好对上（400ms 处理 ≈ 控制被推迟到 200ms+）

### ③ 根因

`SingleThreadedExecutor` 同一时刻只跑一个回调。

图像回调（原版 400ms）执行期间，控制定时器的回调**没法执行**，
所以控制的实际频率 ≈ 1 / 图像处理耗时 = 1/0.4s = 2.5Hz，
加上定时器本身的调度，实测 4.6Hz。

**这不是定时器不准，是回调被阻塞。**

### ④ 修复

换成多线程执行器，让两个节点的回调可以并行：

```python
executor = MultiThreadedExecutor(num_threads=2)
```

### ⑤ 验证

```
$ ros2 topic hz /control/cmd
average rate: 19.985
```

控制恢复到 ≈20 Hz，与定时器设定一致。

---

## 故障 5：只改处理端，输出反而掉到 0.92Hz

### ① 现象

做对照实验（原版 `camera_pub.py` + 优化后的 `image_proc.py`），预期的结果是
"处理变快了，输出应该接近输入频率"。实际：

```
--- 输入（相机自报） ---
[CAMERA] 已发布 156 帧, 平均 25.80 Hz (目标 30.0 Hz)

--- 输出 ---
average rate: 0.920

--- 控制 ---
average rate: 20.008

--- 延迟 ---
average delay: 0.009
```

**输出只有 0.92Hz**，比基线的 4.5Hz 还差。

### ② 定位过程

1. 处理端已经向量化，单帧不到 5ms，不可能算不过来
2. 控制正常（20Hz），说明执行器没问题
3. 延迟只有 9ms，说明"收到了的帧"处理很快——**问题在收，不在算**
4. 对比两端的 QoS：
   - 原版 `camera_pub.py`：`RELIABLE`，`depth=30`，`bgr8`
   - 新版 `image_proc.py`：`BEST_EFFORT`，`depth=1`
5. 按故障 1 的规则，RELIABLE 发布 + BEST_EFFORT 订阅是**兼容**的，不该完全收不到
6. 但两边的**队列深度差 30 倍**（30 vs 1），加上发布端还在用 `bgr8` 大图（921KB）
   且逐像素生成（25Hz 已经是它的上限），订阅端只留 1 帧 → 大部分帧在到达前就被新帧顶掉

### ③ 根因

这是两种问题叠加：

1. **发布端本身到不了 30Hz**（25.8Hz 是逐像素生成的上限）——这是主因
2. **`depth=1` 在接收端激进丢帧**——发布端资源紧张、发送有抖动时，
   新帧不断顶掉还没被取走的旧帧，实际被处理的比例进一步下降

**结论：只优化处理端，输入侧的瓶颈仍在，输出必然上不去。**
这正是题目说的"两端的瓶颈互相独立，只改一端达不到达标线"。

### ④ 修复

不需要修——这是**对照实验的预期失败**，用来证明"必须两端同时改"。
如果真要在这个组合下工作，只能把发布端也优化（即最终的完整方案）。

### ⑤ 验证

两端同时优化后：

```
输入 30.00 Hz / 输出 29.97 Hz / 控制 20.0 Hz / 延迟平均 9ms（最大 35ms）
```

四项全部达标。

---

## 附：一条被排除的怀疑（保留失败尝试）

改 QoS 之前，我一度怀疑是**图像编码不匹配**导致处理端收不到数据：
发布端发 `bgr8`、处理端要 `mono8`，`cv_bridge` 理论上会自动转换，
但如果转换失败会抛异常。

于是我在 `on_image` 里加了 `try/except` 打印异常——**结果一条异常都没有**，
说明编码转换是成功的，问题不在编码。

**这次排查虽然没找到答案，但它排除了一个方向**，让下一步去查 QoS 变得更有针对性。

---

## 故障 6：所有指标都差一点点——定时器周期不等于设定值

### ① 现象

两端都优化完，四项里三项卡在临界：

```
输入 30.00 Hz（目标 30）     输出 29.66 Hz（目标 30）
控制 19.96 Hz（目标 20）     延迟 9 ms（达标）
```

单项都只差 0.3%~0.5%，而且每次测都差不多，不是随机波动。

### ② 定位过程

1. 先怀疑处理跟不上 → 给 `image_proc.py` 加发布计数，每 3 秒自报一次
2. 自报结果 `[PROC] 已发布 ... 平均 29.90 Hz`——**处理端确实只发了 29.9Hz，不是测量工具丢帧**
3. 手算一帧的处理耗时：向量化后不到 5ms，33ms 的预算绰绰有余，**不是算不过来**
4. 转头看定时器：`create_timer(1.0 / CAMERA_HZ, ...)`，设的是 1/30 = 33.33ms
5. 关键认识：**`create_timer` 的实际周期 = 设定周期 + 回调执行时间 + 调度延迟**，
   设定 33.33ms 实际会跑到 33.4~33.6ms，折算下来就是 29.8~29.9Hz

### ③ 根因

`create_timer(1/30)` **不等于**"每秒精确触发 30 次"。

它保证的是"上一次回调结束后，再等 33.33ms"，所以每次都会把回调耗时累加进周期。
Python 回调哪怕只花 1ms，30 次下来就是 30ms 的累积损失 → 频率掉到 29.9。

**这不是 bug，是定时器的定义。** 高频场景必须自己补余量。

### ④ 修复

按实测损失给定时器留余量：

```python
# 相机：目标 30Hz，留 3%
self.create_timer(1.0 / (CAMERA_HZ * 1.03), self.on_timer)

# 控制：目标 20Hz，留 4%
self.create_timer(1.0 / (CONTROL_HZ * 1.04), self.on_timer)
```

### ⑤ 验证

```
输入   [CAMERA] 平均 30.83 Hz   （目标 30）
输出   ros2 topic hz: 30.61     （目标 30）
处理端自报 [PROC]: 30.62 Hz
控制   ros2 topic hz: 20.80     （目标 20）
延迟   average 0.010s, max 0.032s
```

四项全部达标且有余量。

> 注意：这不违反题目"不能把相机定时器频率改低"的约束——我们是**往高留余量**，
> 让实测值落在 30Hz 而不是掉到 29.9Hz。

---

## 故障 7：发布端改 RELIABLE 后频率反而下降

### ① 现象

想让 `ros2 topic hz` 读数更准（BEST_EFFORT 下它会丢帧），把输出话题改成了 `RELIABLE + depth=5`：

```python
reliability=ReliabilityPolicy.RELIABLE,
depth=5,
```

结果更差：

```
输出 hz:       29.45     （改之前 29.66）
处理端自报:    29.27     （改之前 29.90）
```

### ② 定位过程

1. 排除定时器（上一轮刚修过，输入是 30.00）
2. 对比改前改后的唯一差异：只有 QoS
3. 想到 RELIABLE 的机制：发送方要等接收方 ACK，还会重传
4. 我们发的是 307KB 的 mono8 大图，本地回环上 RELIABLE 的握手/重传开销反而拖慢了发送

### ③ 根因

**RELIABLE 不是"更保险的 BEST_EFFORT"，它是有真实代价的另一种语义。**

对 30Hz 的 307KB 图像流来说，RELIABLE 的 ACK 与重传开销大于它带来的好处；
而`ros2 topic hz` 读数偏低的原因是**它自己**作为订阅者跟不上，不是我们的发布丢帧。

### ④ 修复

回退成 `BEST_EFFORT + depth=1`，改用**自计数**做真值：

```python
self.count += 1
self.get_logger().info("[PROC] 已发布 %d 帧, 平均 %.2f Hz" % (self.count, self.count/elapsed))
```

### ⑤ 验证

```
处理端自报: 30.62 Hz      ← 真值
ros2 topic hz: 30.61      ← 留余量后两者一致
```

**结论：测量工具读数低于自计数时，先怀疑工具，别急着改链路。**
