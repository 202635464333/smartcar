# M0-3 ｜ 代码排查

对上一届留下的 sensor_analyzer.py 进行缺陷排查与修复，使其真正完成原本意图：读数据 → 算均值标准差 → 剔除离群值 → 输出清洗结果。

---

## 一、如何运行

```bash
cd M0/M0-3

# 方式一：无参数（默认读写当前目录下的 sensor_data.csv / cleaned_data.csv）
python3 sensor_analyzer.py

# 方式二：显式指定输入输出
python3 sensor_analyzer.py --input sensor_data.csv --output cleaned_data.csv
```

- 输出到 stdout 的摘要包含 `均值 mean = <数值>` 与 `标准差 std = <数值>` 两行
- 默认写入**当前工作目录**的 `cleaned_data.csv`；用 `--output 名字.csv` 可以指定别的文件名或路径（不写死绝对路径），内容为清洗后的 `time,value` 两列
- 正常结束退出码 `0`；异常输入打印中文提示并以退出码 `1` 结束，**不抛栈回溯**

---

## 二、缺陷清单

> 行号为**原始文件**中的行号。前 4 处由本人独立发现并修复，后 6 处中约一半的修复代码由 AI 生成或改写。

| # | 位置（原始行号） | 现象 | 为什么有问题 | 如何修复 |
| :-- | :-- | :-- | :-- | :-- |
| 1 | 第 37 行 | `KeyError: 'Value'`，程序直接崩溃 | csv 表头是小写 `value`，代码写的是大写 `Value`；`DictReader` 的键严格区分大小写 | 改为 `row["value"]` |
| 2 | 第 52 行 | 不报错，但标准差结果明显偏小 | 标准差公式应为「离差平方和的均值再开平方」，此处 `acc += (v - mean)` **漏了平方** | 改为 `acc += (v - mean) ** 2` |
| 3 | 第 53 行 | 不报错，但标准差仍不对 | `std = acc / len(data)` 少了开平方；本人初版写的 `acc**1/2 / len(data)**1/2` 同样错误——`**` 优先级高于 `/`，实际算的是 `acc/2` | 改为 `acc**0.5 / len(data)**0.5`（等价 `sqrt(acc/n)`） |
| 4 | 第 56~58 行 | 离群值剔不干净，结果数量不对 | ① 只判断 `v > mean + 2*std`，**偏小的离群值没处理**；② 在 `for` 循环中 `data.remove(v)`，边遍历边删会**跳过元素** | 改为绝对值判定 `abs(v - mean) <= 2 * std`，并**收集正常值**而非从原列表删除 |
| 5 | 第 61 行 | `FileNotFoundError: '/out/cleaned_data.csv'` | `os.path.join("/", OUTPUT_DIR, OUTPUT_FILE)` 中首个 `"/"` 把路径顶到**硬盘根目录**，该目录不存在且无写入权限 | 改用 `OUTPUT_FILE`，直接写到当前目录（任务书要求） |
| 6 | 第 65~66 行 | `_csv.Error: iterable expected, not float` | `writer.writerow(v)` 传入单个浮点数，csv 要求一行是可迭代对象（列表）；且 `cleaned` 列表**从未被填充**，输出文件只有表头 | 改为 `writer.writerow(row)`，写入 `[时间, 数值]` 两列 |
| 7 | 第 33 行 | 文件句柄未关闭 | `csv.DictReader(open(...))` 把 open 的结果直接传进去，文件**始终没被关闭** | 改用 `with open(...) as f:`（曾因缩进错误导致 `I/O operation on closed file`，已修正） |
| 8 | 第 36~39 行（连带） | 清洗后的数据丢失了时间戳 | `data` 只存数值，`times` 单独存时间，清洗时两者**失去对应关系** | 读取时成对存储 `rows.append([t, v])`，清洗时整对保留 |
| 9 | 第 47 / 53 行 | 空文件（只有表头）时 `ZeroDivisionError` | `len(data) == 0` 时除法崩溃 | 捕获 `ZeroDivisionError`，打印「数据文件为空」并退出码 1 |
| 10 | 全局 | 异常输入直接抛 `Traceback` | 完全没有异常处理 | 用 `try...except` 覆盖 `FileNotFoundError` / `KeyError` / `ValueError` / `ZeroDivisionError`，打印中文提示 + `sys.exit(1)` |

**额外改进**（非缺陷，主动重构）：
- 将脚本拆分为 `load_data` / `calculate_mean` / `calculate_std` / `remove_outliers` / `save_cleaned_data` / `main` 六个函数，消除全局变量
- 增加 `--input` / `--output` 命令行参数（`argparse`，默认值保证无参也可运行）
- 增加 `if __name__ == "__main__":` 入口保护

---

## 三、结果验证

用题目给定的 `sensor_data.csv` 运行：

```
共读取 60 条数据
均值 mean = 50.4315
标准差 std = 18.5033
清洗后剩余 57 条
```

与独立实现（numpy）逐一比对，**完全一致**：

| 指标 | 本程序 | numpy 独立计算 |
| :-- | :-- | :-- |
| 均值 mean | 50.4315 | 50.4315 |
| 标准差 std | 18.5033 | 18.5033 |
| 清洗后条数 | 57 | 57 |

> 说明：`numpy.std` 默认除以 n（总体标准差），与本题「离差平方和 / n 再开平方」的定义一致。

---

## 四、异常输入测试

本人主动构造了以下异常输入进行自测：

| 异常输入 | 输出 | 退出码 |
| :-- | :-- | :-- |
| 数据文件不存在 | 错误：找不到数据文件 | 1 |
| 空文件（只有表头） | 错误：数据文件为空，无法计算 | 1 |
| 列名不符（如 `val` 而非 `value`） | 错误：数据文件缺少 time 或 value 列 | 1 |
| 数据含非数字内容 | 错误：数据中存在无法转换为数字的内容 | 1 |

以上均**未出现栈回溯**。

---

## 五、AI 使用声明

本题约为**一半的工作由 AI 完成**，如实说明如下：

- **本人完成**：独立发现 4 处缺陷（列名大小写、标准差漏平方、开平方算法、离群值单边判定），并构造全部异常输入进行自测
- **AI 完成或改写**：其余 6 处缺陷的定位方向由 AI 提示，其中**约一半的修复代码由 AI 直接生成或改写**
- **本人负责**：运行全部用例，将清洗结果与 numpy 独立实现逐一比对
- 已通读全部代码，答辩时可解释每一处修改的原因
