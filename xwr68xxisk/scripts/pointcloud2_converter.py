#!/usr/bin/env python3
"""
Convert RadarPointCloud messages to PointCloud2 for RViz2 visualization.

This converter adds an 'intensity' field based on SNR values to enable
proper colorization in RViz2. In RViz2, set the PointCloud2 display's
'Color Transformer' to 'Intensity' to see colored points based on signal strength.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header
import numpy as np
import struct
import sys
import os

# Add the parent directory to the path to import xwr68xxisk modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from xwr68xxisk.msg import RadarPointCloud as RadarPointCloudMsg

class PointCloud2Converter(Node):
    """Convert RadarPointCloud to PointCloud2 for RViz2 visualization."""
    
    def __init__(self):
        super().__init__('pointcloud2_converter')
        
        # Declare parameters
        self.declare_parameter('intensity_source', 'snr')  # 'snr' or 'rcs'
        self.intensity_source = self.get_parameter('intensity_source').get_parameter_value().string_value
        
        # Subscribe to RadarPointCloud
        self.subscription = self.create_subscription(
            RadarPointCloudMsg,
            'radar_point_cloud',
            self.radar_callback,
            10
        )
        
        # Publish PointCloud2
        self.publisher = self.create_publisher(
            PointCloud2,
            'radar_point_cloud_viz',
            10
        )
        
        self.get_logger().info("PointCloud2 converter started")
        self.get_logger().info("Subscribing to: /radar_point_cloud")
        self.get_logger().info("Publishing to: /radar_point_cloud_viz")
        self.get_logger().info(f"Using '{self.intensity_source}' for intensity colorization")
    
    def radar_callback(self, msg: RadarPointCloudMsg):
        """Convert RadarPointCloud to PointCloud2."""
        if msg.num_points == 0:
            return
            
        # Create PointCloud2 message
        cloud_msg = PointCloud2()
        cloud_msg.header = msg.header
        cloud_msg.height = 1
        cloud_msg.width = msg.num_points
        
        # Define fields including radar-specific data and intensity for RViz2 colorization
        fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
            PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
            PointField(name='velocity', offset=16, datatype=PointField.FLOAT32, count=1),
            PointField(name='snr', offset=20, datatype=PointField.FLOAT32, count=1),
            PointField(name='rcs', offset=24, datatype=PointField.FLOAT32, count=1),
        ]
        
        cloud_msg.fields = fields
        cloud_msg.point_step = 28  # 7 fields * 4 bytes each
        cloud_msg.row_step = cloud_msg.point_step * cloud_msg.width
        cloud_msg.is_dense = True
        
        # Pack data
        data = []
        for i in range(msg.num_points):
            # Use selected field as intensity for RViz2 colorization
            if self.intensity_source == 'rcs':
                intensity = msg.rcs[i]
            else:  # default to SNR
                intensity = msg.snr[i]
            
            data.append(struct.pack('fffffff', 
                                   msg.x[i], msg.y[i], msg.z[i], intensity,
                                   msg.velocity[i], msg.snr[i], msg.rcs[i]))
        
        cloud_msg.data = b''.join(data)
        
        # Publish
        self.publisher.publish(cloud_msg)
        self.get_logger().info(f"Converted {msg.num_points} points to PointCloud2 with intensity colorization", once=True)

def main():
    rclpy.init()
    node = PointCloud2Converter()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main() 