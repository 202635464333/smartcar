import yaml          #读取配置文件
import csv           #读取表格数据
import math          #数学计算
import sys           #处理系统级错误

def load_config(config_yaml): 
    with open(config_yaml) as f:    #打开了某个文件
        cfg = yaml.safe_load(f)     #safe_load把文件对象f里的YAML文本解析成Python对象
        csv_path = cfg["input_csv"]   #大字典里的一个数据
        col_x = cfg["columns"]["x"]   #大字典套一个小字典
        col_y = cfg["columns"]["y"]
    return csv_path, col_x, col_y

def load_csv(csv_path, col_x, col_y):
    xs = []      #定义一个新变量(空列表)
    ys = []

    with open(csv_path) as f:
        reader = csv.DictReader(f)    #csv.DictReader把f中遍历成字典
        for row in reader:
            xs.append(float(row[col_x]))  #字典套字典，提取数据(float)
            ys.append(float(row[col_y]))

    n = len(xs)    #统计追加的数据总数量
    return xs, ys, n

def mean(xs,ys,n):
    sum_x = 0.0
    sum_y = 0.0    #float使得出现小数点
    for i in range(n):
        sum_x = sum_x + xs[i]  #累加求和，用于计算平均值
        sum_y = sum_y + ys[i]  #疑点：数据总和可能不同，导致ys后面的数没被加上
    #求和
    mean_x = sum_x / n
    mean_y = sum_y / n
    return mean_x, mean_y

def correlation(xs,ys,n,mean_x,mean_y):
    dx = 0.0
    dy = 0.0
    prod = 0.0
    for i in range(n):   #n依旧是f（分解成几行字典）中数据总和
        a = xs[i] - mean_x #每份数据-平均数
        b = ys[i] - mean_y
        dx = dx + a * a #离差平方和（该列数据的总波动）
        dy = dy + b * b
        prod = prod + a * b #离差乘积和（协方差分子）

    denom = math.sqrt(dx * dy) #总波动乘积开平方，作归一化分母
    r = prod / denom
    return r

def main():
    try:
        csv_path, col_x, col_y = load_config("config.yaml")
        xs, ys, n = load_csv(csv_path, col_x, col_y)
        mean_x, mean_y = mean(xs, ys, n)
        r = correlation(xs, ys, n, mean_x, mean_y)
        print("n =", n)
        print("mean_x =", mean_x)
        print("mean_y =", mean_y)
        print("r =", r)
    except FileNotFoundError as e:
        print(f"错误：找不到文件 {e.filename}，请检查路径")
        sys.exit(1)
    except KeyError as e:
        print(f"错误：数据中不存在配置的列 {e}，请检查 config.yaml 的 columns 字段")
        sys.exit(1)
    except ValueError as e:
        print("错误：数据中存在无法转换为数字的内容")
        sys.exit(1)
    except ZeroDivisionError:
        print("错误：数据为空或某列取值恒定，相关系数无定义")
        sys.exit(1)
    except Exception as e:
        print(f"未预期的错误：{e}")
        sys.exit(1)
if __name__ == "__main__":
    main()
