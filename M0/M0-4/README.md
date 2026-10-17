# M0-4 ｜ 任务调度模拟器（TaskScheduler）

按依赖关系调度一批"模拟任务"的命令行程序：读配置文件 → 按拓扑顺序执行 → 每个任务按 `success_rate` 随机成功或失败、失败自动重试 → 终端实时彩色输出 → 运行结束生成 JSON 报告。

不依赖 ROS、不依赖 GUI，全程在终端运行。

---

## 一、环境与依赖

- Windows 11 + WSL2 + Ubuntu 22.04
- Python 3.10（项目内使用 `.venv` 虚拟环境）
- 唯一第三方依赖：`PyYAML`（见 `requirements.txt`）

从零跑起来的完整步骤：

```bash
cd ~/smartcar/M0/M0-4

# 1. 创建虚拟环境（已创建过可跳过）
uv venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装依赖
uv pip install -r requirements.txt
```

> 注意：本项目用 `uv` 管理环境。`uv venv` 创建的环境默认**不带 pip**，因此安装依赖必须用 `uv pip install`；直接敲 `pip install` 会装进系统 Python，虚拟环境里依然 `ModuleNotFoundError`。

---

## 二、运行示例

### 示例 1 ｜ 最简运行（其余参数全部用默认值）

```bash
python3 scheduler.py --config tasks_demo.yaml
```

- 使用配置里的 `timeout: 15`
- 报告写到当前目录的 `report.json`
- 不固定随机种子，每次运行成败结果都可能不同

### 示例 2 ｜ 考核现场的标准命令（四个参数齐全）

```bash
python3 scheduler.py --config tasks_demo.yaml --timeout 15 --report report.json --seed 42
```

- `--timeout 15` 覆盖配置文件里的超时时间
- `--seed 42` 固定随机种子，**同一台机器上重复执行，成败结果逐条一致**
- 预期：7 个任务在 12~13 秒内跑完，退出码 `0`

### 示例 3 ｜ 演示超时（换成 JSON 配置 + 缩短超时）

```bash
python3 scheduler.py --config tasks_demo.json --timeout 3 --report result_timeout.json --seed 7
```

- 配置换成 `.json`（JSON 是 YAML 的子集，`yaml.safe_load` 可以直接解析）
- 3 秒内没跑完的任务全部标记 `TIMEOUT`
- 报告照常生成，`"timed_out": true`，进程以退出码 `1` 结束

---

## 三、参数说明

| 参数 | 是否必填 | 说明 | 默认值 |
| :-- | :-- | :-- | :-- |
| `--config` | **是** | 任务配置文件路径，支持 `.yaml` / `.yml` / `.json` | 无，不填则 argparse 报错并以退出码 2 结束 |
| `--timeout` | 否 | 全局超时（秒），**优先级高于配置文件里的 `timeout`** | 取配置文件的 `timeout`，都没有则 15 |
| `--report` | 否 | 报告输出路径 | `report.json` |
| `--seed` | 否 | 随机种子，填入后同种子可复现同一次结果 | 不固定（按系统时间取起点） |

两个设计取舍：

- `--config` 设为 `required=True`，因为程序离开配置文件无法工作；缺参数时的报错和退出由 argparse 自动完成，不需要手写判断。
- `--timeout` 让命令行覆盖配置，是为了现场临时测试超时逻辑时不必修改配置文件。

---

## 四、配置文件格式

```yaml
timeout: 15          # 默认全局超时（秒），可被 --timeout 覆盖

tasks:
  - name: Init
    duration: 0.5        # 预期耗时（秒）
    success_rate: 1.0    # 成功率 0.0 ~ 1.0
    dependencies: []     # 前置任务名列表，没有前置就写空列表

  - name: Navigate
    duration: 2.5
    success_rate: 0.8
    dependencies: ["Init"]

  - name: Place
    duration: 1.0
    success_rate: 0.85
    dependencies: ["Grasp", "AvoidObstacle"]   # 多个前置，必须全部成功
```

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `name` | string | 任务名，全局唯一 |
| `duration` | float | 预期耗时，程序用 `time.sleep(duration)` 模拟 |
| `success_rate` | float | 成功率，必须在 0 ~ 1 之间 |
| `dependencies` | list | 前置任务名列表；写 `dependencies:` 留空按"无依赖"处理 |

任务在文件里的**书写顺序不影响执行顺序**。程序通过反复扫描配置，自动排出合法的执行次序（同一份配置可能存在多种合法顺序）。

---

## 五、输出说明

### 5.1 终端彩色日志

| 颜色 | 标签 | 含义 |
| :-- | :-- | :-- |
| 绿 | `[SUCCESS]` | 任务成功（首次成功或重试后成功） |
| 黄 | `[RETRY]` | 本次尝试失败，还有重试机会 |
| 红 | `[FAILED]` | 首次 + 2 次重试共 3 次全部失败 |
| 蓝 | `[SKIPPED]` | 前置任务未成功，本任务未执行 |
| 紫 | `[TIMEOUT]` | 全局超时，本任务未执行 |

单次运行的典型输出：

```
[SUCCESS] Init（第 1 次尝试）
[SUCCESS] Navigate（第 1 次尝试）
...
[RETRY] AvoidObstacle 第 1 次尝试失败，准备重试
[RETRY] AvoidObstacle 第 2 次尝试失败，准备重试
[FAILED] AvoidObstacle 连续 3 次失败
[SKIPPED] Place（前置 AvoidObstacle 未成功）
[SKIPPED] ReturnHome（前置 Place 未成功）
```

> 重试耗尽的任务记为 **FAILED**；只有**依赖它的下游**任务记为 **SKIPPED**。`RETRY` 只是过程提示，不作为任务最终状态写入报告。

### 5.2 报告文件

默认写到 `report.json`，结构如下（取自 `--seed 42` 的一次真实运行）：

```json
{
  "timeout": 15.0,
  "total_duration": 12.39,
  "timed_out": false,
  "tasks": [
    { "name": "Init",         "status": "SUCCESS", "attempts": 1, "duration": 0.5 },
    { "name": "Navigate",     "status": "SUCCESS", "attempts": 1, "duration": 3.38 },
    { "name": "AvoidObstacle","status": "FAILED",  "attempts": 3, "duration": 6.0 },
    { "name": "Place",        "status": "SKIPPED", "attempts": 0, "duration": 0 },
    { "name": "ReturnHome",   "status": "SKIPPED", "attempts": 0, "duration": 0 }
  ]
}
```

| 字段 | 说明 |
| :-- | :-- |
| `timeout` | 本次生效的超时阈值 |
| `total_duration` | 程序从开始到结束的**真实墙钟耗时**（秒） |
| `timed_out` | 是否因超时提前终止 |
| `tasks[].status` | 最终状态，只有 `SUCCESS` / `FAILED` / `SKIPPED` / `TIMEOUT` 四种 |
| `tasks[].attempts` | 实际尝试次数；未执行的任务为 0 |
| `tasks[].duration` | 该任务从开始到结束的真实耗时（含重试等待） |

`duration` 记的是实测时间而不是配置里的 `duration`，因为重试会让它翻倍，WSL 的系统调度也会带来几十毫秒到几百毫秒的抖动——报告要反映真实开销，而不是照抄预期值。因此**同 seed 两次运行，状态和尝试次数完全一致，`total_duration` 允许有小幅差异**。

---

## 六、实现要点

1. **拓扑排序**：用 `status` 字典记录已完成的任务，`while` 循环反复扫描整份配置，每轮只执行"前置全部成功"的任务；扫描到没有任何新进展时即结束。
2. **重试**：每个任务 `for n in range(1, 4)`，成功立即 `break`；3 次都失败则记 `FAILED`。
3. **失败传播**：判断前置时用 `status[dep] != "SUCCESS"`，失败会沿着依赖链自动向上下游传染，无需额外的传播循环。
4. **超时控制**：`start = time.time()` 掐表，**每处理一个任务前**检查一次墙钟时间，超过阈值就把尚未出结果的任务批量标 `TIMEOUT` 并停止调度。
5. **卡死检测**：如果一整轮扫描下来没有任何任务产出结果，说明依赖关系成环，打印卡住的任务名并以退出码 1 结束，避免 `while` 空转死循环。
6. **可复现**：`random.seed(seed)` 只在程序开头调用一次，固定随机数序列的起点，从而固定每个任务抽到的判定值。

---

## 七、异常处理与退出码

| 情况 | 提示 | 退出码 |
| :-- | :-- | :-- |
| 命令行参数缺失或写错 | argparse 自动打印用法 | 2 |
| 配置文件不存在 | `[ERROR] 找不到配置文件：xxx` | 1 |
| YAML / JSON 语法错误 | `[ERROR] 配置文件语法有误` | 1 |
| 缺少 `tasks` 字段 / 任务列表为空 | `[ERROR] 配置文件里没有 tasks 列表` | 1 |
| 任务缺少必需字段 | `[ERROR] 有任务缺少字段 xxx` | 1 |
| `duration` 为负 / `success_rate` 超出 0~1 | 指出具体任务与非法值 | 1 |
| 依赖了不存在的任务名 | `[ERROR] 任务 A 依赖了不存在的任务：xxx` | 1 |
| 依赖关系成环 | 列出卡住的任务名 | 1 |
| 超时提前终止 | 报告正常生成，`timed_out: true` | 1 |
| 全部正常结束 | 打印报告路径与总耗时 | 0 |

所有异常都输出中文提示，**不抛 Traceback**。退出码 1 与 2 分开，便于脚本区分"运行出错"和"命令敲错"。

---

## 八、验收记录

| # | 场景 | 结果 | 退出码 |
| :-- | :-- | :-- | :-- |
| 1 | 标准命令 `--seed 42` | 7 个任务跑完，报告生成 | 0 |
| 2 | 同 seed 连跑两次 | `status` 与 `attempts` 逐条一致 | 0 |
| 3 | 配置文件不存在 | 中文提示，无 Traceback | 1 |
| 4 | YAML 语法错误 | 中文提示 | 1 |
| 5 | 依赖成环（A↔B） | 列出卡住的任务 A、B | 1 |
| 6 | 依赖不存在的任务 | 指出任务名与非法依赖 | 1 |
| 7 | 缺少 `success_rate` | 指出缺失字段 | 1 |
| 8 | `success_rate: 1.5` | 指出越界 | 1 |
| 9 | `--timeout 0` | 提示必须大于 0 | 1 |
| 10 | `--timeout 3` | 剩余任务标 TIMEOUT，`timed_out: true` | 1 |
| 11 | 缺 `--config` | argparse 报错 | 2 |
| 12 | 配置换成 `.json` | 与 yaml 结果一致 | 0 |

---

## 九、AI 使用声明

> **本题代码主体由 AI 助手生成或改写，本人负责提出需求、运行验证与结果核对。**

| 环节 | 实际完成方式 |
| :-- | :-- |
| 题目理解、依赖关系梳理、拓扑序推导 | AI 讲解概念，本人在纸上独立推导并核对 |
| `scheduler.py` 代码 | 由 AI 生成或改写；本人逐个功能提出要求，运行后把问题反馈给 AI |
| 虚拟环境与依赖安装 | 本人按指导执行命令 |
| 运行与验证 | 所有测试命令由本人执行，输出由本人观察后反馈 |
| `README.md`、`requirements.txt` | AI 起草，本人核对内容 |
| 代码理解 | 本人已通读全部代码，答辩时可解释各模块的作用 |

### 计分方式确认

本题代码主体由 AI 编写/改写，参照题目对 AI 使用题的规则（现场答辩分数占比提高到 80，其余按比例缩减），本题同样按 **答辩 80 分 + 其余维度 20 分** 的权重申报，本人已知悉并接受。

- **代码是否经过验证**：是。12 项验收命令均由本人执行，输出与报告由本人逐条核对
- **代码是否经过仔细研究**：是。本人已通读全部代码，能解释各模块作用、关键行（93/95/112/115）的判定逻辑与设计取舍
