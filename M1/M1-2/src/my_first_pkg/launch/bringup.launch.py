"""M1-2 一键启动脚本

用法：
    ros2 launch my_first_pkg bringup.launch.py                    # 同时起两组 robot1 + robot2
    ros2 launch my_first_pkg bringup.launch.py dual:=false        # 只起一组（默认 robot1）
    ros2 launch my_first_pkg bringup.launch.py dual:=false namespace:=my_robot
    ros2 launch my_first_pkg bringup.launch.py dual:=false params_file:=/path/to/x.yaml
    ros2 launch my_first_pkg bringup.launch.py params_file:=/nope.yaml   # 演示错误提示
"""

import os

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    Shutdown,
)
from launch.event_handlers import OnProcessStart
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace

# 两组实例各自默认的参数文件
DEFAULT_PARAMS = {
    'robot1': os.path.expanduser('~/study/M1/M1-2/params_robot1.yaml'),
    'robot2': os.path.expanduser('~/study/M1/M1-2/params_robot2.yaml'),
}


def _build_group(ns, params_file, use_sim_time):
    """生成一组三节点：A、B 直接起，C 由 B 的启动事件触发"""
    common_params = [params_file, {'use_sim_time': use_sim_time}]

    node_a = Node(
        package='my_first_pkg',
        executable='node_a_sensor',
        name='node_a_sensor',
        parameters=common_params,
        output='screen',
    )
    node_b = Node(
        package='my_first_pkg',
        executable='node_b_filter',
        name='node_b_filter',
        parameters=common_params,
        output='screen',
    )
    node_c = Node(
        package='my_first_pkg',
        executable='node_c_alarm',
        name='node_c_alarm',
        namespace=ns,   # 事件回调里不继承 GroupAction 的命名空间，必须显式指定
        parameters=common_params,
        output='screen',
    )

    return GroupAction([
        PushRosNamespace(ns),          # 本组所有节点都挂到这个命名空间下
        node_a,
        node_b,
        # 节点C 必须在节点B 完全启动之后才启动
        RegisterEventHandler(
            OnProcessStart(target_action=node_b, on_start=[node_c])
        ),
    ])


def _launch_setup(context):
    """OpaqueFunction：launch 时执行，先校验参数文件再展开节点"""
    dual = LaunchConfiguration('dual').perform(context).lower() in ('true', '1', 'yes')
    use_sim_time = (LaunchConfiguration('use_sim_time').perform(context).lower()
                    in ('true', '1', 'yes'))
    namespace = LaunchConfiguration('namespace').perform(context)
    params_file = LaunchConfiguration('params_file').perform(context)

    if dual:
        groups = {
            'robot1': params_file or DEFAULT_PARAMS['robot1'],
            'robot2': DEFAULT_PARAMS['robot2'],
        }
    else:
        groups = {namespace: params_file or DEFAULT_PARAMS['robot1']}

    # 校验参数文件：缺失时给出可读提示并退出，不产生 Python 栈回溯
    for ns, path in groups.items():
        if not os.path.isfile(path):
            return [
                LogInfo(msg='=' * 62),
                LogInfo(msg=f'[启动失败] 参数文件不存在：{path}'),
                LogInfo(msg=f'           命名空间 {ns} 需要该文件'),
                LogInfo(msg='           请检查 params_file 参数，或确认文件已生成'),
                LogInfo(msg='=' * 62),
                Shutdown(reason='params_file 校验失败'),
            ]

    actions = [LogInfo(msg=f'[启动] 共 {len(groups)} 组：{", ".join(sorted(groups))}')]
    for ns in sorted(groups):
        actions.append(LogInfo(msg=f'[启动] {ns}  →  {groups[ns]}'))
        actions.append(_build_group(ns, groups[ns], use_sim_time))
    return actions


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'dual', default_value='true',
            description='true：同时启动 robot1 与 robot2 两组；false：只启动一组'),
        DeclareLaunchArgument(
            'namespace', default_value='robot1',
            description='dual=false 时使用的命名空间'),
        DeclareLaunchArgument(
            'params_file', default_value='',
            description='YAML 参数文件路径，留空则使用默认文件'),
        DeclareLaunchArgument(
            'use_sim_time', default_value='false',
            description='是否使用仿真时间'),
        OpaqueFunction(function=_launch_setup),
    ])
