#!/usr/bin/env python3
"""
Diagnostic script to check available TF2 frames and transforms.
Useful for debugging coordinate frame issues.
"""

import rclpy
from rclpy.node import Node
import tf2_ros
from rclpy.duration import Duration


class TransformChecker(Node):
    """Simple node to check available transforms and frames."""
    
    def __init__(self):
        super().__init__('transform_checker')
        
        # Initialize TF2
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # Wait a moment for transforms to be available
        self.timer = self.create_timer(2.0, self.check_transforms)
        
    def check_transforms(self):
        """Check and print available transforms."""
        
        self.get_logger().info("=== Transform Checker ===")
        
        # Get all available frames
        try:
            frames = self.tf_buffer.all_frames_as_string()
            self.get_logger().info("Available frames:")
            for line in frames.split('\n'):
                if line.strip():
                    self.get_logger().info(f"  {line}")
        except Exception as e:
            self.get_logger().warning(f"Could not get frame list: {e}")
        
        # Check specific transforms we need
        transforms_to_check = [
            ('odom', 'base_link'),
            ('base_link', 'radar_link'),
            ('odom', 'radar_link'),
        ]
        
        self.get_logger().info("\nChecking specific transforms:")
        
        for target, source in transforms_to_check:
            try:
                transform = self.tf_buffer.lookup_transform(
                    target, source,
                    rclpy.time.Time(),
                    timeout=Duration(seconds=1.0)
                )
                self.get_logger().info(f"✓ {source} → {target}: Available")
                
                # Print transform details
                t = transform.transform.translation
                r = transform.transform.rotation
                self.get_logger().info(f"  Translation: ({t.x:.3f}, {t.y:.3f}, {t.z:.3f})")
                self.get_logger().info(f"  Rotation: ({r.x:.3f}, {r.y:.3f}, {r.z:.3f}, {r.w:.3f})")
                
            except tf2_ros.TransformException as e:
                self.get_logger().warning(f"✗ {source} → {target}: {e}")
        
        # Shutdown after one check
        self.get_logger().info("\nTransform check complete.")
        rclpy.shutdown()


def main():
    rclpy.init()
    node = TransformChecker()
    rclpy.spin(node)


if __name__ == '__main__':
    main() 