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

with open("tasks_demo.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

status = {}                                    # 记每个任务的最终结果
while len(status) < len(data["tasks"]):
    for task in data["tasks"]:
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
                print(f"跳过：{name}（前置 {dep} 未成功）")
                can_run = False
                break

        if not can_run:                        # 不能执行（要么等，要么已跳过）
            continue

        # 到这里：所有前置都 SUCCESS，可以执行 + 重试
        ok = False
        for n in range(1, 4):
            time.sleep(task["duration"])
            if random.random() < task["success_rate"]:
                print(f"成功：{name}（第 {n} 次尝试）")
                ok = True
                break
            print(f"失败：{name} 第 {n} 次尝试")

        if ok:
            status[name] = "SUCCESS"
        else:
            status[name] = "FAILED"
            print(f"{name} 连续 3 次失败")

            
