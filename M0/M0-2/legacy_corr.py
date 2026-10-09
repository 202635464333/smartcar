import yaml          #读取配置文件
import csv           #读取表格数据
import math          #数学计算

CONFIG_PATH = "config.yaml"     #定义变量

with open(CONFIG_PATH) as f:    #打开了某个文件
    cfg = yaml.safe_load(f)     #safe_load把文件对象f里的YAML文本解析成Python对象
#并将f中的数据字典化给变量
csv_path = cfg["input_csv"]   #大字典里的一个数据
col_x = cfg["columns"]["x"]   #大字典套一个小字典
col_y = cfg["columns"]["y"]

xs = []      #定义一个新变量(空列表)
ys = []

with open(csv_path) as f:
    reader = csv.DictReader(f)    #csv.DictReader把f中遍历成字典
    for row in reader:
        xs.append(float(row[col_x]))  #字典套字典，提取数据(float)
        ys.append(float(row[col_y]))

n = len(xs)    #统计追加的数据总数量

sum_x = 0.0
sum_y = 0.0    #float使得出现小数点
for i in range(n):
    sum_x = sum_x + xs[i]  #xs中第i+1份数据（即索引为i的数据）加入到sum_x中
    sum_y = sum_y + ys[i]  #疑点：数据总和可能不同，导致ys后面的数没被加上
#求和
mean_x = sum_x / n
mean_y = sum_y / n
#平均数
dx = 0.0
dy = 0.0
prod = 0.0
for i in range(n):   #n依旧是f（分解成几行字典）中数据总和
    a = xs[i] - mean_x #每份数据-平均数
    b = ys[i] - mean_y
    dx = dx + a * a #加权平均数的分子
    dy = dy + b * b
    prod = prod + a * b #某种算法，所得结果不知道有什么用

denom = math.sqrt(dx * dy) #两组数据（加权平均数的分子）相乘
r = prod / denom

print("n =", n) #x中的数据总数
print("mean_x =", mean_x) #平均数
print("mean_y =", mean_y)
print("r =", r) #某种运算结果
