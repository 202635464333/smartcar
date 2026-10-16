import yaml
import random
import time

with open("tasks_demo.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

done=[]
while len(done) < len(data["tasks"]):
    for task in data["tasks"]:
        if task["name"] in done:
            continue
        all_ready = True                   
        for dep in task["dependencies"]:    
            if dep not in done:
                all_ready = False           

        if all_ready:                       
            time.sleep(task["duration"])
            if random.random() < task["success_rate"]:
                print(f"成功：{task['name']}")
            else:
                print(f"失败：{task['name']}")
            done.append(task["name"])
            
