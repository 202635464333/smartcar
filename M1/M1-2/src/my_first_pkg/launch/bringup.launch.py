from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """一键启动三个节点"""
    return LaunchDescription([
        DeclareLaunchArgument(
        'namespace',
        default_value='robot1',
        description='所有节点的命名空间',
        ),
        DeclareLaunchArgument(
        'params_file',
        default_value='/home/lenovo/study/M1/M1-2/params_robot1.yaml',
        description='YAML 参数文件路径',
        ),


        Node(
            package='my_first_pkg',
            executable='node_a_sensor',
            name='node_a_sensor',
            namespace=LaunchConfiguration('namespace'),
            output='screen',
        ),
        Node(
            package='my_first_pkg',
            executable='node_b_filter',
            name='node_b_filter',
            namespace=LaunchConfiguration('namespace'),
            parameters=[LaunchConfiguration('params_file')],
            output='screen',
        ),
        Node(
            package='my_first_pkg',
            executable='node_c_alarm',
            name='node_c_alarm',
            namespace=LaunchConfiguration('namespace'),
            parameters=[LaunchConfiguration('params_file')],
            output='screen',
        ),
    ])
