#!/usr/bin/env python3

"""
ROS2 launch file for radar replay node.
This replays recorded radar data from CSV and YAML files.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for radar replay node."""
    
    # Get package directory
    pkg_dir = get_package_share_directory('xwr68xxisk')
    
    # Declare launch arguments
    recording_directory_arg = DeclareLaunchArgument(
        'recording_directory',
        default_value='/Users/juhasch/git/xwr68xxisk/recordings',
        description='Directory containing the recording files'
    )
    
    base_filename_arg = DeclareLaunchArgument(
        'base_filename',
        default_value='radar_data_20250517_134646',
        description='Base filename for the recording (without extension)'
    )
    
    replay_rate_arg = DeclareLaunchArgument(
        'replay_rate_hz',
        default_value='10.0',
        description='Replay rate in Hz'
    )
    
    loop_replay_arg = DeclareLaunchArgument(
        'loop_replay',
        default_value='true',
        description='Whether to loop the replay continuously'
    )
    
    use_original_timestamps_arg = DeclareLaunchArgument(
        'use_original_timestamps',
        default_value='false',
        description='Whether to use original timestamps from recording'
    )
    
    time_scale_factor_arg = DeclareLaunchArgument(
        'time_scale_factor',
        default_value='1.0',
        description='Time scale factor when using original timestamps (1.0 = real-time, 0.5 = half speed, 2.0 = double speed)'
    )
    
    frame_id_arg = DeclareLaunchArgument(
        'frame_id',
        default_value='radar_link',
        description='Frame ID for the radar data'
    )
    
    point_cloud_topic_arg = DeclareLaunchArgument(
        'point_cloud_topic',
        default_value='radar_point_cloud',
        description='Topic name for radar point cloud data'
    )
    
    radar_info_topic_arg = DeclareLaunchArgument(
        'radar_info_topic',
        default_value='radar_info',
        description='Topic name for radar info/configuration data'
    )
    
    config_file_arg = DeclareLaunchArgument(
        'config_file',
        default_value=PathJoinSubstitution([pkg_dir, 'config', 'radar_replay_params.yaml']),
        description='Path to parameter file'
    )
    
    # Create radar replay node
    radar_replay_node = Node(
        package='xwr68xxisk',
        executable='radar_replay_node.py',
        name='radar_replay_node',
        parameters=[
            LaunchConfiguration('config_file'),
            {
                'recording_directory': LaunchConfiguration('recording_directory'),
                'base_filename': LaunchConfiguration('base_filename'),
                'replay_rate_hz': LaunchConfiguration('replay_rate_hz'),
                'loop_replay': LaunchConfiguration('loop_replay'),
                'use_original_timestamps': LaunchConfiguration('use_original_timestamps'),
                'time_scale_factor': LaunchConfiguration('time_scale_factor'),
                'frame_id': LaunchConfiguration('frame_id'),
                'point_cloud_topic': LaunchConfiguration('point_cloud_topic'),
                'radar_info_topic': LaunchConfiguration('radar_info_topic'),
            }
        ],
        output='screen',
        emulate_tty=True,
    )
    
    return LaunchDescription([
        recording_directory_arg,
        base_filename_arg,
        replay_rate_arg,
        loop_replay_arg,
        use_original_timestamps_arg,
        time_scale_factor_arg,
        frame_id_arg,
        point_cloud_topic_arg,
        radar_info_topic_arg,
        config_file_arg,
        radar_replay_node,
    ]) 