#!/usr/bin/env python3
"""
Example script demonstrating how to use the refactored RadarData class.

This script shows how to:
1. Connect to a radar device
2. Use the iterator to process frames in real-time
3. Work with RadarPointCloud objects
"""

import time
import logging
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Import radar modules
from parse import RadarData, AWR2544Data
from point_cloud import RadarPointCloud

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MockRadarConnection:
    """
    Mock radar connection for demonstration purposes.
    
    This class simulates a radar connection that produces random point cloud data.
    """
    
    def __init__(self):
        """Initialize the mock radar connection."""
        self._running = True
        self.frame_number = 0
        
    def is_connected(self):
        """Check if the radar is connected."""
        return True
        
    @property
    def is_running(self):
        """Check if the radar is running."""
        return self._running
        
    def read_frame(self):
        """
        Read a frame from the radar.
        
        Returns:
            Tuple containing header and payload
        """
        # Simulate some processing time
        time.sleep(0.1)
        
        # Create a random number of points (between 10 and 50)
        num_points = np.random.randint(10, 50)
        
        # Create header
        header = {
            'frame_number': self.frame_number,
            'num_detected_obj': 1,  # One TLV for point cloud
            'timestamp': int(time.time() * 1000)
        }
        
        # Create payload with TLV structure
        # TLV type 1 (point cloud) - 4 bytes
        # TLV length (num_points * 16) - 4 bytes
        # Point cloud data (x, y, z, v) - num_points * 16 bytes
        tlv_type = (1).to_bytes(4, byteorder='little')
        tlv_length = (num_points * 16).to_bytes(4, byteorder='little')
        
        # Generate random point cloud data
        payload = bytearray(tlv_type + tlv_length)
        
        for _ in range(num_points):
            # Random x, y, z, v values
            x = np.random.uniform(-5, 5)
            y = np.random.uniform(0, 10)
            z = np.random.uniform(-2, 2)
            v = np.random.uniform(-3, 3)
            
            # Pack as float32 (4 bytes each)
            payload.extend(np.float32(x).tobytes())
            payload.extend(np.float32(y).tobytes())
            payload.extend(np.float32(z).tobytes())
            payload.extend(np.float32(v).tobytes())
        
        # Increment frame number
        self.frame_number += 1
        
        return header, payload
        
    def stop(self):
        """Stop the radar."""
        self._running = False


def process_frames_with_iterator(radar_connection, max_frames=10):
    """
    Process radar frames using the iterator.
    
    Args:
        radar_connection: RadarConnection instance
        max_frames: Maximum number of frames to process
    """
    logger.info("Processing frames with iterator...")
    
    # Create RadarData object
    radar_data = RadarData(radar_connection)
    
    # Process frames using iterator
    frame_count = 0
    for point_cloud in radar_data:
        frame_count += 1
        logger.info(f"Frame {frame_count}: {point_cloud.num_points} points detected")
        
        # Print some statistics
        if point_cloud.num_points > 0:
            logger.info(f"  Range: min={point_cloud.range.min():.2f}m, max={point_cloud.range.max():.2f}m")
            logger.info(f"  Velocity: min={point_cloud.velocity.min():.2f}m/s, max={point_cloud.velocity.max():.2f}m/s")
            
            # Get Cartesian coordinates
            x, y, z = point_cloud.to_cartesian()
            logger.info(f"  X: min={x.min():.2f}m, max={x.max():.2f}m")
            logger.info(f"  Y: min={y.min():.2f}m, max={y.max():.2f}m")
            logger.info(f"  Z: min={z.min():.2f}m, max={z.max():.2f}m")
        
        # Stop after max_frames
        if frame_count >= max_frames:
            break
    
    logger.info(f"Processed {frame_count} frames")


def visualize_point_cloud(radar_connection):
    """
    Visualize a single radar frame as a 3D point cloud.
    
    Args:
        radar_connection: RadarConnection instance
    """
    logger.info("Visualizing point cloud...")
    
    # Create RadarData object and get point cloud
    radar_data = RadarData(radar_connection)
    point_cloud = radar_data.to_point_cloud()
    
    if point_cloud.num_points == 0:
        logger.warning("No points detected in the frame")
        return
    
    # Get Cartesian coordinates
    x, y, z = point_cloud.to_cartesian()
    
    # Create 3D plot
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    
    # Plot points
    scatter = ax.scatter(x, y, z, c=point_cloud.velocity, cmap='coolwarm', 
                         marker='o', s=30, alpha=0.8)
    
    # Add colorbar for velocity
    cbar = plt.colorbar(scatter)
    cbar.set_label('Velocity (m/s)')
    
    # Set labels and title
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')
    ax.set_title('Radar Point Cloud')
    
    # Set axis limits
    ax.set_xlim([-5, 5])
    ax.set_ylim([0, 10])
    ax.set_zlim([-2, 2])
    
    # Show plot
    plt.tight_layout()
    plt.show()


def main():
    """Main function."""
    logger.info("Starting radar example...")
    
    # Create mock radar connection
    radar_connection = MockRadarConnection()
    
    try:
        # Process frames with iterator
        process_frames_with_iterator(radar_connection, max_frames=5)
        
        # Visualize point cloud
        visualize_point_cloud(radar_connection)
        
    finally:
        # Stop radar
        radar_connection.stop()
        logger.info("Radar stopped")


if __name__ == "__main__":
    main() 