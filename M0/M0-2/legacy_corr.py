import yaml          #读取配置文件
import csv           #读取表格数据
import math          #数学计算

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
        sum_x = sum_x + xs[i]  #离差乘积和（协方差分子）
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

def main():#将全部函数封装进一个大的函数里，执行大函数时，小函数才能被执行，体现统一性
    csv_path, col_x, col_y = load_config("config.yaml")
    xs, ys, n = load_csv(csv_path, col_x, col_y)
    mean_x, mean_y = mean(xs, ys, n)
    r = correlation(xs, ys, n, mean_x, mean_y)
    print("n =", n) #x中的数据总数
    print("mean_x =", mean_x) #平均数
    print("mean_y =", mean_y)
    print("r =", r) #皮尔逊相关系数，范围[-1,1]

if __name__ == "__main__":#这样文件被别人import时不会自动执行——这是“能跑”和“工程能接受”的分界线
    main()