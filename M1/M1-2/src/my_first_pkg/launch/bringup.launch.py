"""M1-2 一键启动脚本：把 M1-1 的三个节点用一条命令启动，而且能同时启动两组。

和 M1-1 的关系：
    M1-1 写了 4 个 .py（零件）→ 要开 4 个终端各敲一条 ros2 run
    M1-2 只加一个 launch（产线）→ 一条命令把零件全装上，还能装两条产线互不干扰

用法：
    ros2 launch my_first_pkg bringup.launch.py                    # 起两组 robot1 + robot2（共 6 节点）
    ros2 launch my_first_pkg bringup.launch.py dual:=false        # 只起一组
    ros2 launch my_first_pkg bringup.launch.py dual:=false namespace:=my_robot
    ros2 launch my_first_pkg bringup.launch.py dual:=false params_file:=/path/x.yaml
    ros2 launch my_first_pkg bringup.launch.py params_file:=/nope.yaml   # 演示报错

三段结构：
    第1段  import + 常量     准备工具
    第2段  _build_group      造"一组节点"（A、B、C 三个）
    第3段  _launch_setup     决定起几组、校验文件、拼出最终清单（核心）
    第4段  generate_launch_description   入口，声明 4 个可传参数
"""

# ==================== 第 1 段：拿工具 ====================

import os                                                       # 为了用 os.path.isfile 判断文件存不存在

from launch import LaunchDescription                            # launch 的"清单容器"：装要启动的东西
from launch.actions import (                                    # launch 的"动作"工具（不涉及 ROS 的）
    DeclareLaunchArgument,                                      # 声明一个可从命令行传的参数
    GroupAction,                                                # 把多个动作打包成一组
    LogInfo,                                                    # 在终端打一行日志
    OpaqueFunction,                                             # "延迟执行"：在 launch 时才跑我们自己的函数
    RegisterEventHandler,                                       # 注册事件监听（用来控制启动顺序）
    Shutdown,                                                   # 主动退出 launch
)
from launch.event_handlers import OnProcessStart                # 事件：某个进程启动之后
from launch.substitutions import LaunchConfiguration            # 读取参数当前的值（占位符）
from launch_ros.actions import Node, PushRosNamespace           # Node=启动一个ROS节点；PushRosNamespace=给一组节点加命名空间
                                                                # ★ PushRosNamespace 在 launch_ros 里，不在 launch.actions 里
                                                                #   写错模块会报 ImportError: cannot import name 'PushRosNamespace'


# 两组实例各自的默认参数文件（写绝对路径，免得受当前目录影响）
DEFAULT_PARAMS = {
    'robot1': os.path.expanduser('~/study/M1/M1-2/params_robot1.yaml'),   # expanduser 把 ~ 换成 /home/lenovo
    'robot2': os.path.expanduser('~/study/M1/M1-2/params_robot2.yaml'),
}
                                                          # 这是个字典：键是命名空间名，值是配置文件路径

# ==================== 第 2 段：造"一组节点" ====================


def _build_group(ns, params_file, use_sim_time):
    """给一个命名空间，造出 A、B、C 三个节点，打包成一组返回。

    参数：
        ns           命名空间名，如 'robot1'
        params_file  这一组要用的 yaml 路径
        use_sim_time 是否使用仿真时间
    """
    common_params = [params_file, {'use_sim_time': use_sim_time}]
    # ↑ 三个节点共用的参数清单。
    #   列表第一个是文件路径（ROS 会去读那个 yaml），第二个是临时覆盖的单个参数。
    #   两者顺序有意义：后写的会覆盖先写的。

    node_a = Node(                                              # 节点A：传感器
        package='my_first_pkg',                                 # 去哪个包找
        executable='node_a_sensor',                             # 可执行文件名（setup.py 里登记的那个）
        name='node_a_sensor',                                   # 节点名，必须显式给，不依赖默认值
        parameters=common_params,                               # 用上面那份参数
        output='screen',                                        # 日志直接打到屏幕（不加这句日志会被吞掉）
    )

    node_b = Node(                                              # 节点B：滤波
        package='my_first_pkg',
        executable='node_b_filter',
        name='node_b_filter',
        parameters=common_params,
        output='screen',
    )

    node_c = Node(                                              # 节点C：报警
        package='my_first_pkg',
        executable='node_c_alarm',
        name='node_c_alarm',
        namespace=ns,                                           # ★ 这里必须显式写命名空间
                                                                #   因为它是被"事件"启动的，不会继承下面 PushRosNamespace 的作用域
                                                                #   不写的话会跑到根命名空间，变成 /node_c_alarm，验收时数不出 6 个
        parameters=common_params,
        output='screen',
    )

    return GroupAction([                                        # 把下面这些打包成"一组"，一起生效
        PushRosNamespace(ns),                                   # ① 给本组所有节点套上命名空间，节点名变成 /robot1/xxx
        node_a,                                                 # ② 启动节点A
        node_b,                                                 # ③ 启动节点B
        RegisterEventHandler(                                   # ④ 注册一个事件监听
            OnProcessStart(                                     #    事件 = "某个进程启动了"
                target_action=node_b,                           #    监听谁 = 节点B
                on_start=[node_c],                              #    启动后干什么 = 再启动节点C
            )                                                   #    这样保证 C 一定在 B 之后起来
        ),
    ])

# ==================== 第 3 段：决定起几组、校验、拼清单（核心） ====================


def _launch_setup(context):
    """OpaqueFunction 调用的函数，在 launch 那一刻执行。

    为什么需要它：参数文件路径只有在启动时才知道，普通的声明式写法读不到。
    有了它就能"先检查文件在不在，再决定启动什么"，出错时给可读提示而不是一堆栈回溯。
    """
    dual = LaunchConfiguration('dual').perform(context).lower() in ('true', '1', 'yes')
    # ↑ 读出 dual 参数的值，转小写，看是不是 true/1/yes 之一 → 得到 True 或 False

    use_sim_time = (LaunchConfiguration('use_sim_time').perform(context).lower()
                    in ('true', '1', 'yes'))
    # ↑ 同理，读 use_sim_time

    namespace = LaunchConfiguration('namespace').perform(context)      # 读命名空间名（只起一组时用）
    params_file = LaunchConfiguration('params_file').perform(context)  # 读指定的 yaml 路径（可能为空字符串）

    if dual:                                                    # 如果 dual （同时启用两辆车）是 true（默认就是）
        groups = {                                              # 字典里放 2 个 → 待会循环 2 次 → 起 2 组
            'robot1': params_file or DEFAULT_PARAMS['robot1'],   # 用户指定了就用指定的，没指定用默认的
            'robot2': DEFAULT_PARAMS['robot2'],                  # robot2 固定用自己那份（0.5）
        }
    else:                                                       # dual 是 false
        groups = {namespace: params_file or DEFAULT_PARAMS['robot1']}
                                                                # 字典里只放 1 个 → 起 1 组

    for ns, path in groups.items():                             # 逐个检查参数文件在不在
        if not os.path.isfile(path):                            # isfile = 这个路径是不是一个存在的文件
            return [                                            # 不在 → 不启动任何节点，只打提示然后退出
                LogInfo(msg='=' * 62),
                LogInfo(msg=f'[启动失败] 参数文件不存在：{path}'),
                LogInfo(msg=f'           命名空间 {ns} 需要该文件'),
                LogInfo(msg='           请检查 params_file 参数，或确认文件已生成'),
                LogInfo(msg='=' * 62),
                Shutdown(reason='params_file 校验失败'),          # ★ 优雅退出，不抛 Python 异常
            ]                                                   #   所以终端里看不到栈回溯，只有上面这几行提示

    actions = [LogInfo(msg=f'[启动] 共 {len(groups)} 组：{", ".join(sorted(groups))}')]
    # ↑ 准备要返回的清单。第一项是"打一行字，告诉你起了几组"

    for ns in sorted(groups):                                   # 遍历字典的键（命名空间名），sorted 只为输出顺序稳定
        actions.append(LogInfo(msg=f'[启动] {ns}  →  {groups[ns]}'))
        # ↑ 追加一项：打一行"这一组用哪个文件"

        actions.append(_build_group(ns, groups[ns], use_sim_time))
        #   执行任务
        # ↑ 追加一项：用第 2 段的函数造出这一组节点
        #   groups[ns] 是"按名字取值"——拿到这个命名空间对应的 yaml 路径

    return actions                                              # 把清单交回去，launch 照着执行

# ==================== 第 4 段：入口，声明可传参数 ====================


def generate_launch_description():
    """ros2 launch 会自动调用这个函数，拿到它返回的清单去执行。"""
    return LaunchDescription([

        DeclareLaunchArgument(                                  # 声明参数 dual
            'dual', default_value='true',                       # 默认 true → 不加参数就是默认起两组
            description='true：同时启动 robot1 与 robot2；false：只启动一组'),

        DeclareLaunchArgument(                                  # 声明参数 namespace
            'namespace', default_value='robot1',                # 只起一组时默认用 robot1
            description='dual=false 时使用的命名空间'),

        DeclareLaunchArgument(                                  # 声明参数 params_file
            'params_file', default_value='',                    # 默认空字符串（没给数据） → 表示"用内置默认文件"
            description='YAML 参数文件路径，留空则使用默认文件'),

        DeclareLaunchArgument(                                  # 声明参数 use_sim_time
            'use_sim_time', default_value='false',              # M1-3 回放 bag 时才需要 true
            description='是否使用仿真时间'),

        OpaqueFunction(function=_launch_setup),                 # ★ 把第 3 段那个函数交给 launch
                                                                #   它会在启动那一刻执行，返回真正的清单（防止参数没读完就开始跑代码引发报错）
    ])
