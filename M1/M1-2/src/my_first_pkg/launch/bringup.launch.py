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
            output='screen',
        ),
        Node(
            package='my_first_pkg',
            executable='node_c_alarm',
            name='node_c_alarm',
            namespace=LaunchConfiguration('namespace'),
            output='screen',
        ),
    ])
