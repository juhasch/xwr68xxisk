#!/usr/bin/env python3
"""
Transform radar point cloud data from radar_link frame to target frame (e.g., odom).
"""

import rclpy
from rclpy.node import Node
from rclpy.time import Time
from rclpy.duration import Duration
import tf2_ros
import tf2_geometry_msgs
from geometry_msgs.msg import PointStamped, TransformStamped
import numpy as np
import sys
import os

# Add the parent directory to the path to import xwr68xxisk modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from xwr68xxisk.msg import RadarPointCloud as RadarPointCloudMsg

class RadarTransformNode(Node):
    """Transform radar point cloud data to target coordinate frame."""
    
    def __init__(self):
        super().__init__('radar_transform_node')
        
        # Declare parameters
        self.declare_parameter('target_frame', 'odom')
        self.declare_parameter('source_frame', 'radar_link')
        self.declare_parameter('transform_timeout', 1.0)
        
        # Get parameters
        self.target_frame = self.get_parameter('target_frame').get_parameter_value().string_value
        self.source_frame = self.get_parameter('source_frame').get_parameter_value().string_value
        self.transform_timeout = self.get_parameter('transform_timeout').get_parameter_value().double_value
        
        # Initialize TF2
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Subscribe to radar point cloud
        self.subscription = self.create_subscription(
            RadarPointCloudMsg,
            'radar_point_cloud',
            self.radar_callback,
            10
        )
        
        # Publish transformed point cloud
        self.publisher = self.create_publisher(
            RadarPointCloudMsg,
            'radar_point_cloud_transformed',
            10
        )
        
        self.get_logger().info("Radar transform node started")
        self.get_logger().info(f"Transforming from '{self.source_frame}' to '{self.target_frame}'")
        self.get_logger().info("Input topic: /radar_point_cloud")
        self.get_logger().info("Output topic: /radar_point_cloud_transformed")
        
        # Counter for transform failures
        self.transform_failures = 0
        self.total_messages = 0
    
    def radar_callback(self, msg: RadarPointCloudMsg):
        """Transform radar point cloud to target frame."""
        self.total_messages += 1
        
        if msg.num_points == 0:
            # Forward empty messages as-is but with updated frame
            transformed_msg = msg
            transformed_msg.header.frame_id = self.target_frame
            self.publisher.publish(transformed_msg)
            return
        
        try:
            # Get transform from source to target frame
            # Use Time(0) to get the latest available transform instead of exact timestamp
            transform = self.tf_buffer.lookup_transform(
                self.target_frame,
                self.source_frame,
                rclpy.time.Time(),  # Use latest available transform
                timeout=Duration(seconds=self.transform_timeout)
            )
            
            # Transform all points
            transformed_points = self.transform_points(msg, transform)
            
            # Create new message with transformed data
            transformed_msg = RadarPointCloudMsg()
            transformed_msg.header = msg.header
            transformed_msg.header.frame_id = self.target_frame
            transformed_msg.num_points = msg.num_points
            
            # Set transformed coordinates
            transformed_msg.x = transformed_points[:, 0].tolist()
            transformed_msg.y = transformed_points[:, 1].tolist()
            transformed_msg.z = transformed_points[:, 2].tolist()
            
            # Copy radar-specific data (unchanged by coordinate transform)
            transformed_msg.velocity = msg.velocity
            transformed_msg.snr = msg.snr
            transformed_msg.rcs = msg.rcs
            
            # Publish transformed message
            self.publisher.publish(transformed_msg)
            
            # Log success (only occasionally to avoid spam)
            if self.total_messages % 100 == 1:
                self.get_logger().info(f"Successfully transformed {msg.num_points} points to {self.target_frame} frame")
                
        except tf2_ros.TransformException as e:
            self.transform_failures += 1
            if self.transform_failures % 10 == 1:  # Log every 10th failure to avoid spam
                self.get_logger().warning(f"Transform failed ({self.transform_failures}/{self.total_messages}): {e}")
                if "odom" in str(e).lower():
                    self.get_logger().warning("Hint: Make sure your robot is publishing the odom→base_link transform")
                    self.get_logger().warning("This is typically done by robot localization (nav2, robot_localization, etc.)")
            
            # Forward original message unchanged
            self.publisher.publish(msg)
    
    def transform_points(self, msg: RadarPointCloudMsg, transform: TransformStamped) -> np.ndarray:
        """Transform radar points using the given transform."""
        # Extract translation and rotation from transform
        t = transform.transform.translation
        r = transform.transform.rotation
        
        # Convert quaternion to rotation matrix
        rotation_matrix = self.quaternion_to_rotation_matrix(r.x, r.y, r.z, r.w)
        
        # Create points array
        points = np.array([msg.x, msg.y, msg.z]).T  # Shape: (n_points, 3)
        
        # Apply rotation
        rotated_points = points @ rotation_matrix.T
        
        # Apply translation
        translation = np.array([t.x, t.y, t.z])
        transformed_points = rotated_points + translation
        
        return transformed_points
    
    def quaternion_to_rotation_matrix(self, x, y, z, w):
        """Convert quaternion to rotation matrix."""
        # Normalize quaternion
        norm = np.sqrt(x*x + y*y + z*z + w*w)
        x, y, z, w = x/norm, y/norm, z/norm, w/norm
        
        # Compute rotation matrix
        xx, yy, zz = x*x, y*y, z*z
        xy, xz, yz = x*y, x*z, y*z
        wx, wy, wz = w*x, w*y, w*z
        
        R = np.array([
            [1 - 2*(yy + zz), 2*(xy - wz), 2*(xz + wy)],
            [2*(xy + wz), 1 - 2*(xx + zz), 2*(yz - wx)],
            [2*(xz - wy), 2*(yz + wx), 1 - 2*(xx + yy)]
        ])
        
        return R

def main():
    rclpy.init()
    node = RadarTransformNode()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main() 