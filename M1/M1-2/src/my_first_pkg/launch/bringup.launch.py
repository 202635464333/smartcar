from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """一键启动三个节点"""
    return LaunchDescription([
        Node(
            package='my_first_pkg',
            executable='node_a_sensor',
            name='node_a_sensor',
            output='screen',
        ),
        Node(
            package='my_first_pkg',
            executable='node_b_filter',
            name='node_b_filter',
            output='screen',
        ),
        Node(
            package='my_first_pkg',
            executable='node_c_alarm',
            name='node_c_alarm',
            output='screen',
        ),
    ])
