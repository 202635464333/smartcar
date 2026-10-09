"""
M0-2 单元测试

覆盖内容：
1. 完全正相关   -> r 应为  1.0
2. 完全负相关   -> r 应为 -1.0
3. 零方差异常   -> 应抛出 ZeroDivisionError
4. 列名不匹配   -> 应抛出 KeyError

运行方式（在 M0/M0-2 目录下执行）：
    python3 -m pytest tests/ -v
或：
    PYTHONPATH=. python3 tests/test_corr.py
"""

from legacy_corr import load_csv, mean, correlation


def calc_r(xs, ys):
    """小工具：给定两列数据，一步算出相关系数"""
    n = len(xs)
    mx, my = mean(xs, ys, n)
    return correlation(xs, ys, n, mx, my)


def test_r_positive():
    xs, ys = [1, 2, 3], [2, 4, 6]
    mx, my = mean(xs, ys, 3)
    assert abs(correlation(xs, ys, 3, mx, my) - 1.0) < 1e-6
    print("test_r_positive 通过")


def test_r_negative():
    xs, ys = [1, 2, 3], [6, 4, 2]
    assert abs(calc_r(xs, ys) + 1.0) < 1e-6
    print("test_r_negative 通过")


def test_zero_variance():
    """某一列取值恒定时，方差为 0，相关系数无定义"""
    try:
        calc_r([5, 5, 5], [1, 2, 3])
    except ZeroDivisionError:
        print("test_zero_variance 通过")
        return
    assert False, "零方差时应当抛出 ZeroDivisionError"


def test_missing_column():
    """配置指定的列名在数据文件中不存在时，应当报错"""
    try:
        load_csv("sample_data.csv", "不存在的列", "sensor_b")
    except KeyError:
        print("test_missing_column 通过")
        return
    assert False, "列名不匹配时应当抛出 KeyError"


if __name__ == "__main__":
    test_r_positive()
    test_r_negative()
    test_zero_variance()
    test_missing_column()
    print("全部 4 个用例通过")
