#!/usr/bin/env python3
"""
Launch file for radar with coordinate frame transformations.

This launch file:
1. Starts the radar publisher node
2. Sets up static transforms for the radar sensor mounted on a robot
3. Transforms radar data to the odom frame
4. Optionally provides PointCloud2 conversion for RViz2

You need to adjust the static transform parameters for your specific robot setup.
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    """Generate launch description for radar with odom frame transformation."""
    
    # Define launch arguments
    radar_profile_arg = DeclareLaunchArgument(
        'radar_profile',
        default_value='',
        description='Path to radar profile configuration file (.cfg)'
    )
    
    # Robot base frame (adjust if your robot uses different name)
    base_frame_arg = DeclareLaunchArgument(
        'base_frame',
        default_value='base_link',
        description='Robot base frame name'
    )
    
    # Target frame for transformed data
    target_frame_arg = DeclareLaunchArgument(
        'target_frame',
        default_value='odom',
        description='Target frame for radar data transformation'
    )
    
    # Radar mounting position relative to base_link (ADJUST FOR YOUR ROBOT!)
    radar_x_arg = DeclareLaunchArgument(
        'radar_x',
        default_value='0.2',
        description='Radar X position relative to base_link (meters, forward)'
    )
    
    radar_y_arg = DeclareLaunchArgument(
        'radar_y',
        default_value='0.0',
        description='Radar Y position relative to base_link (meters, left)'
    )
    
    radar_z_arg = DeclareLaunchArgument(
        'radar_z',
        default_value='0.1',
        description='Radar Z position relative to base_link (meters, up)'
    )
    
    radar_roll_arg = DeclareLaunchArgument(
        'radar_roll',
        default_value='0.0',
        description='Radar roll rotation (radians)'
    )
    
    radar_pitch_arg = DeclareLaunchArgument(
        'radar_pitch',
        default_value='0.0',
        description='Radar pitch rotation (radians)'
    )
    
    radar_yaw_arg = DeclareLaunchArgument(
        'radar_yaw',
        default_value='0.0',
        description='Radar yaw rotation (radians)'
    )
    
    # Enable PointCloud2 converter for RViz2
    enable_pointcloud2_arg = DeclareLaunchArgument(
        'enable_pointcloud2',
        default_value='true',
        description='Enable PointCloud2 converter for RViz2 visualization'
    )
    
    publish_rate_arg = DeclareLaunchArgument(
        'publish_rate',
        default_value='10.0',
        description='Point cloud publishing rate in Hz'
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
    
    # Radar publisher node
    radar_publisher_node = Node(
        package='xwr68xxisk',
        executable='radar_publisher_node.py',
        name='radar_publisher_node',
        output='screen',
        parameters=[
            {
                'radar_profile': LaunchConfiguration('radar_profile'),
                'frame_id': 'radar_link',  # Always use radar_link as source frame
                'publish_rate': LaunchConfiguration('publish_rate'),
                'auto_connect': True,
                'radar_info_topic': 'radar_info',
                'radar_info_publish_rate': 1.0,
                'transport': LaunchConfiguration('transport'),
                'bridge_control_endpoint': LaunchConfiguration('bridge_control_endpoint'),
                'bridge_data_endpoint': LaunchConfiguration('bridge_data_endpoint'),
            }
        ]
    )
    
    # Static transform: base_link -> radar_link
    # This defines where the radar is mounted on your robot
    base_to_radar_transform = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='base_to_radar_tf',
        arguments=[
            LaunchConfiguration('radar_x'),
            LaunchConfiguration('radar_y'),
            LaunchConfiguration('radar_z'),
            LaunchConfiguration('radar_yaw'),
            LaunchConfiguration('radar_pitch'),
            LaunchConfiguration('radar_roll'),
            LaunchConfiguration('base_frame'),
            'radar_link'
        ]
    )
    
    # Radar transform node: radar_link -> target_frame (e.g., odom)
    radar_transform_node = Node(
        package='xwr68xxisk',
        executable='radar_transform_node.py',
        name='radar_transform_node',
        output='screen',
        parameters=[
            {
                'target_frame': LaunchConfiguration('target_frame'),
                'source_frame': 'radar_link',
                'transform_timeout': 1.0,
            }
        ]
    )
    
    # PointCloud2 converter for RViz2 (optional)
    pointcloud2_converter = Node(
        package='xwr68xxisk',
        executable='pointcloud2_converter.py',
        name='pointcloud2_converter',
        output='screen',
        parameters=[
            {
                'intensity_source': 'snr',  # Use SNR for intensity coloring
            }
        ],
        remappings=[
            ('radar_point_cloud', 'radar_point_cloud_transformed'),  # Use transformed data
        ],
        condition=IfCondition(LaunchConfiguration('enable_pointcloud2'))
    )
    
    # Create launch description
    return LaunchDescription([
        # Arguments
        radar_profile_arg,
        base_frame_arg,
        target_frame_arg,
        radar_x_arg,
        radar_y_arg,
        radar_z_arg,
        radar_roll_arg,
        radar_pitch_arg,
        radar_yaw_arg,
        enable_pointcloud2_arg,
        publish_rate_arg,
        transport_arg,
        bridge_control_endpoint_arg,
        bridge_data_endpoint_arg,
        
        # Information
        LogInfo(
            msg=['Starting radar with odom transformation:',
                 ' - Radar profile: ', LaunchConfiguration('radar_profile'),
                 ' - Transport: ', LaunchConfiguration('transport'),
                 ' - Control endpoint: ', LaunchConfiguration('bridge_control_endpoint'),
                 ' - Data endpoint: ', LaunchConfiguration('bridge_data_endpoint'),
                 ' - Base frame: ', LaunchConfiguration('base_frame'),
                 ' - Target frame: ', LaunchConfiguration('target_frame'),
                 ' - Radar position: (', LaunchConfiguration('radar_x'), ', ',
                 LaunchConfiguration('radar_y'), ', ', LaunchConfiguration('radar_z'), ')',
                 ' - PointCloud2 converter: ', LaunchConfiguration('enable_pointcloud2')]
        ),
        
        # Nodes
        radar_publisher_node,
        base_to_radar_transform,
        radar_transform_node,
        pointcloud2_converter,
    ]) 