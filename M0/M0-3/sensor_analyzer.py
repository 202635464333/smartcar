#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensor_analyzer.py  —— 上一届学长留下的"能用"的脚本

注释（学长原话）：
    "处理一下传感器数据就能用"

原本意图：
    1. 读取 sensor_data.csv（列：time, value）
    2. 计算 value 的平均值、标准差
    3. 剔除离群值（|value - mean| > 2 * std）
    4. 把清洗后的数据保存为 cleaned_data.csv
    5. 打印一份统计摘要

现状：跑不通 / 跑出来数不对。就交给你了。
"""

import csv
import sys           #处理系统级错误
import argparse      #解析命令行参数

INPUT_FILE = "sensor_data.csv"
OUTPUT_FILE = "cleaned_data.csv"
OUTPUT_DIR = "out"  # 输出目录

print("=== 传感器数据分析 ===")

# --- 读取数据 ---
def load_data(input_path):          # ← 改名 + 吃参数
    rows = []                       # ← 函数内部建列表
    with open(input_path, "r", encoding="utf-8-sig") as f:   # utf-8-sig：兼容 Excel 导出的带 BOM 文件
        reader = csv.DictReader(f)
        for row in reader:
            t = float(row["time"])
            v = float(row["value"])
            rows.append([t, v])
    print("共读取 %d 条数据" % len(rows))
    return rows
      
# --- 计算平均值 ---
def calculate_mean(rows):
    total = 0
    for row in rows:
        total += row[1]
    mean = total / len(rows)
    return mean

# --- 计算标准差 ---
def calculate_std(rows, mean):
    acc = 0
    for row in rows:
        acc += (row[1] - mean)**2
    std = acc**0.5 / len(rows)**0.5
    return std

# --- 剔除离群值 ---
def remove_outliers(rows, mean, std):
    cleaned = []
    for row in rows:
        if abs(row[1] - mean) <= 2 * std:
            cleaned.append(row)
    return cleaned

# --- 输出清洗后的数据 ---
def save_cleaned_data(cleaned, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "value"])
        for row in cleaned:
            writer.writerow(row)
    return output_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=INPUT_FILE)
    parser.add_argument("--output", default=OUTPUT_FILE)
    args = parser.parse_args()
    try:
        rows = load_data(args.input)
        mean = calculate_mean(rows)
        std = calculate_std(rows, mean)
        cleaned = remove_outliers(rows, mean, std)
        output_path = save_cleaned_data(cleaned, args.output)  
        print("均值 mean = %.4f" % mean)
        print("标准差 std = %.4f" % std)
        print("清洗后剩余 %d 条" % len(cleaned))
        print("已保存到 %s" % output_path)
    except FileNotFoundError:
        print("错误：找不到数据文件")
        sys.exit(1)
    except KeyError:
        print("错误：数据文件缺少 time 或 value 列")
        sys.exit(1)
    except ValueError:
        print("错误：数据中存在无法转换为数字的内容")
        sys.exit(1)
    except ZeroDivisionError:
        print("错误：数据文件为空，无法计算")
        sys.exit(1)

if __name__ == "__main__":
    main()


