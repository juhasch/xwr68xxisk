#!/usr/bin/env python3
"""
Launch file for the radar publisher node.

This launch file starts the radar publisher node with configurable parameters.
The node publishes both point cloud data and radar configuration information.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    """Generate launch description for radar publisher node."""
    
    # Define launch arguments
    radar_profile_arg = DeclareLaunchArgument(
        'radar_profile',
        default_value='configs/user_profile.cfg',
        description='Path to radar profile configuration file (.cfg)'
    )
    
    frame_id_arg = DeclareLaunchArgument(
        'frame_id',
        default_value='radar_link',
        description='Frame ID for the radar sensor'
    )
    
    publish_rate_arg = DeclareLaunchArgument(
        'publish_rate',
        default_value='10.0',
        description='Point cloud publishing rate in Hz'
    )
    
    auto_connect_arg = DeclareLaunchArgument(
        'auto_connect',
        default_value='true',
        description='Automatically connect to radar on startup'
    )
    
    radar_info_topic_arg = DeclareLaunchArgument(
        'radar_info_topic',
        default_value='radar_info',
        description='Topic name for radar configuration/info messages'
    )
    
    radar_info_publish_rate_arg = DeclareLaunchArgument(
        'radar_info_publish_rate',
        default_value='1.0',
        description='Radar info publishing rate in Hz'
    )
    
    # Network transport arguments
    transport_arg = DeclareLaunchArgument(
        'transport',
        default_value='auto',
        description='Transport type: auto, serial, or network'
    )
    
    bridge_control_endpoint_arg = DeclareLaunchArgument(
        'bridge_control_endpoint',
        default_value='tcp://127.0.0.1:5557',
        description='Bridge control endpoint for network transport'
    )
    
    bridge_data_endpoint_arg = DeclareLaunchArgument(
        'bridge_data_endpoint',
        default_value='tcp://127.0.0.1:5556',
        description='Bridge data endpoint for network transport'
    )
    
    # Define the radar publisher node
    radar_publisher_node = Node(
        package='xwr68xxisk',
        executable='radar_publisher_node.py',
        name='radar_publisher_node',
        output='screen',
        parameters=[
            {
                'radar_profile': LaunchConfiguration('radar_profile'),
                'frame_id': LaunchConfiguration('frame_id'),
                'publish_rate': LaunchConfiguration('publish_rate'),
                'auto_connect': LaunchConfiguration('auto_connect'),
                'radar_info_topic': LaunchConfiguration('radar_info_topic'),
                'radar_info_publish_rate': LaunchConfiguration('radar_info_publish_rate'),
                'transport': LaunchConfiguration('transport'),
                'bridge_control_endpoint': LaunchConfiguration('bridge_control_endpoint'),
                'bridge_data_endpoint': LaunchConfiguration('bridge_data_endpoint'),
            }
        ],
        remappings=[
            ('radar_point_cloud', 'radar_point_cloud'),
            ('radar_info', LaunchConfiguration('radar_info_topic')),
        ]
    )
    
    # Create launch description
    return LaunchDescription([
        radar_profile_arg,
        frame_id_arg,
        publish_rate_arg,
        auto_connect_arg,
        radar_info_topic_arg,
        radar_info_publish_rate_arg,
        transport_arg,
        bridge_control_endpoint_arg,
        bridge_data_endpoint_arg,
        
        LogInfo(
            msg=['Starting radar publisher node with:',
                 ' - Frame ID: ', LaunchConfiguration('frame_id'),
                 ' - Radar profile: ', LaunchConfiguration('radar_profile'),
                 ' - Transport: ', LaunchConfiguration('transport'),
                 ' - Control endpoint: ', LaunchConfiguration('bridge_control_endpoint'),
                 ' - Data endpoint: ', LaunchConfiguration('bridge_data_endpoint'),
                 ' - Point cloud rate: ', LaunchConfiguration('publish_rate'), ' Hz',
                 ' - Radar info rate: ', LaunchConfiguration('radar_info_publish_rate'), ' Hz',
                 ' - Auto connect: ', LaunchConfiguration('auto_connect')]
        ),
        
        radar_publisher_node,
    ]) 