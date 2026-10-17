import argparse
import sys
import yaml
import random
import time
import json

GREEN  = "\033[32m"      # 成功：绿
RED    = "\033[31m"      # 失败 / 报错：红
YELLOW = "\033[33m"      # 重试：黄
BLUE   = "\033[34m"      # 跳过：蓝
PURPLE = "\033[35m"      # 超时：紫
RESET  = "\033[0m"       # 恢复原色（必须加）

if not sys.stdout.isatty():     # 非 TTY（重定向到文件/管道）时降级：不加颜色码
    GREEN = RED = YELLOW = BLUE = PURPLE = RESET = ""


parser = argparse.ArgumentParser(description="TaskScheduler：按依赖关系调度一批模拟任务")
parser.add_argument("--config", required=True, help="任务配置文件，支持 .yaml / .yml / .json")
parser.add_argument("--timeout", type=float, help="全局超时（秒），不填就用配置里的 timeout")
parser.add_argument("--report", default="report.json", help="报告输出路径，默认 report.json")
parser.add_argument("--seed", type=int, help="随机种子，填了就能复现同一次结果")
args = parser.parse_args()

if args.seed is not None:                   # 填了种子，随机结果就可复现
    random.seed(args.seed)

# ---------- 读配置：文件不存在、格式写错，都给中文提示，而不是甩一堆 traceback ----------
try:
    with open(args.config, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
except FileNotFoundError:
    print(f"{RED}[ERROR]{RESET} 找不到配置文件：{args.config}")
    sys.exit(1)
except yaml.YAMLError:
    print(f"{RED}[ERROR]{RESET} 配置文件语法有误（YAML/JSON 格式不对）：{args.config}")
    sys.exit(1)
except UnicodeDecodeError:
    print(f"{RED}[ERROR]{RESET} 配置文件不是 UTF-8 编码，无法读取：{args.config}")
    sys.exit(1)

# ---------- 检查配置内容是否完整 ----------
if not data or "tasks" not in data:
    print(f"{RED}[ERROR]{RESET} 配置文件里没有 tasks 列表：{args.config}")
    sys.exit(1)

if len(data["tasks"]) == 0:
    print(f"{RED}[ERROR]{RESET} 配置文件里的 tasks 列表是空的：{args.config}")
    sys.exit(1)

for task in data["tasks"]:
    for key in ["name", "duration", "success_rate", "dependencies"]:
        if key not in task:
            print(f"{RED}[ERROR]{RESET} 有任务缺少字段 {key}：{task}")
            sys.exit(1)
    if task["dependencies"] is None:        # 写成 "dependencies:" 后面留空，按没有依赖处理
        task["dependencies"] = []
    if task["duration"] < 0:
        print(f"{RED}[ERROR]{RESET} 任务 {task['name']} 的 duration 不能是负数")
        sys.exit(1)
    if task["success_rate"] < 0 or task["success_rate"] > 1:
        print(f"{RED}[ERROR]{RESET} 任务 {task['name']} 的 success_rate 必须在 0~1 之间，"
              f"当前是 {task['success_rate']}")
        sys.exit(1)

names = []                                  # 把所有任务名收起来，用来查"依赖了不存在的任务"
for task in data["tasks"]:
    names.append(task["name"])

for task in data["tasks"]:
    for dep in task["dependencies"]:
        if dep not in names:
            print(f"{RED}[ERROR]{RESET} 任务 {task['name']} 依赖了不存在的任务：{dep}")
            sys.exit(1)

# ---------- 准备开工 ----------
start = time.time()                                     # 掐表：记下开始的那一刻
timeout = args.timeout if args.timeout is not None else data.get("timeout", 15)

try:
    timeout = float(timeout)
except (TypeError, ValueError):
    print(f"{RED}[ERROR]{RESET} 超时时间不是数字：{timeout}")
    sys.exit(1)

if timeout <= 0:
    print(f"{RED}[ERROR]{RESET} 超时时间必须大于 0，当前是 {timeout}")
    sys.exit(1)

status = {}                                     # 记每个任务的最终结果
records = []                                    # 每个任务的详细记录，最后写进报告
stopped = False                                 # 开关：是否已被迫收工


def finish_timeout():
    """超时收尾：立即终止，把还没出结果的任务全部标 TIMEOUT"""
    for t in data["tasks"]:
        nm = t["name"]
        if nm not in status:
            status[nm] = "TIMEOUT"
            print(f"{PURPLE}[TIMEOUT]{RESET} {nm} 未执行")
            records.append({"name": nm, "status": "TIMEOUT",
                            "attempts": 0, "duration": 0,
                            "started_at": None, "ended_at": None})


while len(status) < len(data["tasks"]) and not stopped:
    before = len(status)                        # 这一轮开始前，已经有几个任务出结果了
    for task in data["tasks"]:
        if time.time() - start > timeout:       # 检查点一：每个任务处理前，看一次表
            finish_timeout()                    # 还没出结果的，全部标 TIMEOUT
            stopped = True                      # 拨开关，让 while 也停下来
            break                               # 跳出 for

        name = task["name"]
        if name in status:                      # 已经有结果了，跳过
            continue

        can_run = True                          # 开关：本轮能不能执行它
        for dep in task["dependencies"]:
            if dep not in status:               # 前置还没出结果 → 先等，这轮不做它
                can_run = False
                break
            if status[dep] != "SUCCESS":        # 前置失败/被跳过 → 本任务跳过
                status[name] = "SKIPPED"
                print(f"{BLUE}[SKIPPED]{RESET} {name}（前置 {dep} 未成功）")
                records.append({"name": name, "status": "SKIPPED",
                                "attempts": 0, "duration": 0,
                                "started_at": None, "ended_at": None})
                can_run = False
                break

        if not can_run:                         # 不能执行（要么等，要么已跳过）
            continue

        # 到这里：所有前置都 SUCCESS，可以执行 + 重试
        task_start = time.time()                # 这个任务单独计时（绝对时间戳）
        ok = False
        ran_out = False                         # 这个任务执行到一半超时了吗
        for n in range(1, 4):
            time.sleep(task["duration"])
            if time.time() - start > timeout:   # 检查点二：sleep 之后再看一次表
                print(f"{PURPLE}[TIMEOUT]{RESET} {name} 执行中超时，立即终止")
                ran_out = True
                break
            if random.random() < task["success_rate"]:
                print(f"{GREEN}[SUCCESS]{RESET} {name}（第 {n} 次尝试）")
                ok = True
                break
            if n < 3:
                print(f"{YELLOW}[RETRY]{RESET} {name} 第 {n} 次尝试失败，准备重试")
            else:
                print(f"{RED}[FAILED]{RESET} {name} 连续 3 次失败")

        ended = time.time()
        if ran_out:                             # 执行到一半被掐：本任务记 TIMEOUT
            status[name] = "TIMEOUT"
            records.append({"name": name, "status": "TIMEOUT", "attempts": n,
                            "duration": round(ended - task_start, 2),
                            "started_at": task_start, "ended_at": ended})
            stopped = True
            finish_timeout()                    # 剩下的任务也全部终止
        else:
            status[name] = "SUCCESS" if ok else "FAILED"
            records.append({"name": name, "status": status[name], "attempts": n,
                            "duration": round(ended - task_start, 2),
                            "started_at": task_start, "ended_at": ended})

    # 一整轮扫完，一个任务都没出结果 → 说明卡住了（依赖成环）
    if len(status) == before and not stopped:
        stuck = []
        for t in data["tasks"]:
            if t["name"] not in status:
                stuck.append(t["name"])
        print(f"{RED}[ERROR]{RESET} 任务卡住了：依赖关系成环，谁也等不到谁")
        print("卡住的任务：" + "、".join(stuck))
        sys.exit(1)

report = {
    "timeout": stopped or (time.time() - start > timeout),   # 布尔：是否超时（按契约）
    "total_duration": round(time.time() - start, 2),
    "tasks": records,
}

try:
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
except OSError:
    print(f"{RED}[ERROR]{RESET} 报告文件写不进去：{args.report}（目录不存在或没有权限）")
    sys.exit(1)

total = report["total_duration"]
print()
print(f"报告已写入 {args.report}，总耗时 {total} 秒")

if report["timeout"]:                           # 超时属于异常收工，退出码给 1
    sys.exit(1)
