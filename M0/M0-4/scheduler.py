# {
#   "timeout": 15,
#   "tasks": [
#     { "name": "Init",          "duration": 0.5, "success_rate": 1.0,  "dependencies": [] },
#     { "name": "Navigate",      "duration": 2.5, "success_rate": 0.8,  "dependencies": ["Init"] },
#     { "name": "DetectQR",      "duration": 1.5, "success_rate": 0.7,  "dependencies": ["Navigate"] },
#     { "name": "Grasp",         "duration": 1.0, "success_rate": 0.9,  "dependencies": ["DetectQR"] },
#     { "name": "AvoidObstacle", "duration": 2.0, "success_rate": 0.6,  "dependencies": ["Navigate"] },
#     { "name": "Place",         "duration": 1.0, "success_rate": 0.85, "dependencies": ["Grasp", "AvoidObstacle"] },
#     { "name": "ReturnHome",    "duration": 2.5, "success_rate": 0.95, "dependencies": ["Place"] }
#   ]
# }

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


with open("tasks_demo.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

start = time.time()            # 掐表：记下开始的那一刻
timeout = data["timeout"]      # 从清单读超时上限

status = {}                                     # 记每个任务的最终结果
records = []                                    # 每个任务的详细记录，最后写进报告
stopped = False                                 # 开关：是否已被迫收工
while len(status) < len(data["tasks"]) and not stopped:
    for task in data["tasks"]:
        if time.time() - start > timeout:       # 每个任务处理前，都看一次表
            for t in data["tasks"]:             # 还没出结果的，全部标 TIMEOUT
                if t["name"] not in status:
                    status[t["name"]] = "TIMEOUT"
                    print(f"{PURPLE}[TIMEOUT]{RESET} {t['name']} 未执行")
                    records.append({"name": t["name"], "status": "TIMEOUT",
                                    "attempts": 0, "duration": 0})
            stopped = True                      # 拨开关，让 while 也停下来
            break                               # 跳出 for

        name = task["name"]
        if name in status:                     # 已经有结果了，跳过
            continue

        can_run = True                         # 开关：本轮能不能执行它
        for dep in task["dependencies"]:
            if dep not in status:              # 前置还没出结果 → 先等
                can_run = False
                break
            if status[dep] != "SUCCESS":       # 前置失败/被跳过 → 本任务跳过
                status[name] = "SKIPPED"
                print(f"{BLUE}[SKIPPED]{RESET} {name}（前置 {dep} 未成功）")
                records.append({"name": name, "status": "SKIPPED",
                                "attempts": 0, "duration": 0})
                can_run = False
                break

        if not can_run:                        # 不能执行（要么等，要么已跳过）
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

with open("report.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print()
print(f"报告已写入 report.json，总耗时 {report['total_duration']} 秒")
