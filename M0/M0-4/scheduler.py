import argparse
import yaml
import random
import time
import json

GREEN  = "\033[32m"      # 成功：绿
RED    = "\033[31m"      # 失败：红
YELLOW = "\033[33m"      # 重试：黄
BLUE   = "\033[34m"      # 跳过：蓝
PURPLE = "\033[35m"      # 超时：紫
RESET  = "\033[0m"       # 恢复原色（必须加）


parser = argparse.ArgumentParser(description="TaskScheduler：按依赖关系调度一批模拟任务")
parser.add_argument("--config", required=True, help="任务配置文件，支持 .yaml / .yml / .json")
parser.add_argument("--timeout", type=float, help="全局超时（秒），不填就用配置里的 timeout")
parser.add_argument("--report", default="report.json", help="报告输出路径，默认 report.json")
parser.add_argument("--seed", type=int, help="随机种子，填了就能复现同一次结果")
args = parser.parse_args()

if args.seed is not None:                   # 填了种子，随机结果就可复现
    random.seed(args.seed)

with open(args.config, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

start = time.time()                                     # 掐表：记下开始的那一刻
timeout = args.timeout if args.timeout is not None else data.get("timeout", 15)

status = {}                                     # 记每个任务的最终结果
records = []                                    # 每个任务的详细记录，最后写进报告
stopped = False                                 # 开关：是否已被迫收工
while len(status) < len(data["tasks"]) and not stopped:
    for task in data["tasks"]:
        if time.time() - start > timeout:       # 每个任务处理前，都看一次表
            for t in data["tasks"]:             # 还没出结果的，全部标 TIMEOUT
                nm = t["name"]
                if nm not in status:
                    status[nm] = "TIMEOUT"
                    print(f"{PURPLE}[TIMEOUT]{RESET} {nm} 未执行")
                    records.append({"name": nm, "status": "TIMEOUT",
                                    "attempts": 0, "duration": 0})
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
                                "attempts": 0, "duration": 0})
                can_run = False
                break

        if not can_run:                         # 不能执行（要么等，要么已跳过）
            continue

        # 到这里：所有前置都 SUCCESS，可以执行 + 重试
        task_start = time.time()                # 这个任务单独计时
        ok = False
        for n in range(1, 4):
            time.sleep(task["duration"])
            if random.random() < task["success_rate"]:
                print(f"{GREEN}[SUCCESS]{RESET} {name}（第 {n} 次尝试）")
                ok = True
                break
            if n < 3:
                print(f"{YELLOW}[RETRY]{RESET} {name} 第 {n} 次尝试失败，准备重试")
            else:
                print(f"{RED}[FAILED]{RESET} {name} 连续 3 次失败")

        if ok:
            status[name] = "SUCCESS"
        else:
            status[name] = "FAILED"
        records.append({"name": name, "status": status[name], "attempts": n,
                        "duration": round(time.time() - task_start, 2)})

report = {
    "timeout": timeout,
    "total_duration": round(time.time() - start, 2),
    "timed_out": stopped,
    "tasks": records,
}

with open(args.report, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

total = report["total_duration"]
print()
print(f"报告已写入 {args.report}，总耗时 {total} 秒")
