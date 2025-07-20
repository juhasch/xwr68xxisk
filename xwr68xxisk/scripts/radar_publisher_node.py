#!/usr/bin/env python3
"""
ROS2 node to publish radar point cloud data from TI mmWave sensors.

This node connects to a TI mmWave radar sensor and publishes point cloud data
using a custom RadarPointCloud message format that includes position, velocity,
SNR, RCS, and other radar-specific information.
"""

import sys
import os
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from std_msgs.msg import Header, String
import numpy as np
import threading
import time
from typing import Optional, Dict, Any
import logging

# Add the parent directory to the path to import xwr68xxisk modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from xwr68xxisk.radar import RadarConnection, create_radar, RadarConnectionError
from xwr68xxisk.parse import RadarData
from xwr68xxisk.point_cloud import RadarPointCloud
from xwr68xxisk.msg import RadarPointCloud as RadarPointCloudMsg
from xwr68xxisk.msg import RadarInfo as RadarInfoMsg
from builtin_interfaces.msg import Time as TimeMsg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RadarPublisherNode(Node):
    """ROS2 node that publishes radar point cloud data."""

    def __init__(self):
        """Initialize the radar publisher node."""
        super().__init__('radar_publisher_node')
        
        # Declare parameters
        self.declare_parameter('radar_profile', '')
        self.declare_parameter('frame_id', 'radar_link')
        self.declare_parameter('publish_rate', 10.0)
        self.declare_parameter('auto_connect', True)
        self.declare_parameter('radar_info_topic', 'radar_info')
        self.declare_parameter('radar_info_publish_rate', 1.0)  # Publish info less frequently
        
        # Get parameters
        self.radar_profile = self.get_parameter('radar_profile').value
        self.frame_id = self.get_parameter('frame_id').value
        self.publish_rate = self.get_parameter('publish_rate').value
        self.auto_connect = self.get_parameter('auto_connect').value
        self.radar_info_topic = self.get_parameter('radar_info_topic').value
        self.radar_info_publish_rate = self.get_parameter('radar_info_publish_rate').value
        
        # Initialize variables
        self.radar: Optional[RadarConnection] = None
        self.is_connected = False
        self.is_running = False
        self.data_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.radar_info_published = False
        self.last_info_publish_time = 0.0
        
        # Set up QoS profile for real-time data
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
        
        # Create point cloud publisher
        self.point_cloud_publisher = self.create_publisher(
            RadarPointCloudMsg,
            'radar_point_cloud',
            qos_profile
        )
        
        # Create radar info publisher (less frequent updates)
        info_qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,  # Latch the last message
            depth=1
        )
        self.radar_info_publisher = self.create_publisher(
            RadarInfoMsg,
            self.radar_info_topic,
            info_qos_profile
        )
        
        # Initialize radar connection
        if self.auto_connect:
            self.connect_radar()
        
        # Log initialization
        self.get_logger().info(f'Radar publisher node initialized')
        self.get_logger().info(f'Point cloud topic: radar_point_cloud')
        self.get_logger().info(f'Radar info topic: {self.radar_info_topic}')
        self.get_logger().info(f'Frame ID: {self.frame_id}')
        self.get_logger().info(f'Point cloud publish rate: {self.publish_rate} Hz')
        self.get_logger().info(f'Radar info publish rate: {self.radar_info_publish_rate} Hz')
    
    def connect_radar(self) -> bool:
        """
        Connect to the radar sensor.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.get_logger().info('Attempting to connect to radar...')
            
            # Create radar connection
            self.radar = create_radar()
            
            if self.radar_profile:
                self.get_logger().info(f'Using radar profile: {self.radar_profile}')
                self.radar.connect(self.radar_profile)
            else:
                self.get_logger().info('Using default radar configuration')
                # Use empty string for default configuration
                self.radar.connect("")
            
            # Connection was successful if no exception was raised
            self.get_logger().info('Successfully connected to radar')
            self.is_connected = True
            
            # Publish initial radar info
            self.publish_radar_info()
            
            # Start data acquisition thread
            self.start_data_thread()
            
            return True
                
        except RadarConnectionError as e:
            self.get_logger().error(f'Radar connection error: {e}')
            return False
        except Exception as e:
            self.get_logger().error(f'Unexpected error connecting to radar: {e}')
            return False
    
    def publish_radar_info(self):
        """Publish radar configuration and sensor information."""
        if not self.radar:
            return
            
        msg = RadarInfoMsg()
        
        # Set header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        
        # Sensor identification (placeholders - would need to extract from radar)
        msg.sensor_model = "XWR68xx"  # Could detect from radar type
        msg.firmware_version = ""     # Would need to query from radar
        msg.serial_number = ""        # Would need to query from radar
        
        # Current sensor status
        msg.sensor_status = 0 if self.is_connected else 2  # 0=OK, 2=ERROR
        msg.sensor_info = f"Connected: {self.is_connected}, Streaming: {self.is_running}"
        msg.is_connected = self.is_connected
        msg.is_streaming = self.is_running
        
        # Extract radar parameters (would need to parse from radar configuration)
        radar_params = getattr(self.radar, 'radar_params', {})
        
        # Radar configuration parameters (with defaults if not available)
        msg.carrier_frequency_ghz = float(60.0)  # Example value
        msg.bandwidth_mhz = float(3999.68)      # Example value
        msg.frame_period_ms = float(radar_params.get('framePeriod', 100.0))
        msg.num_tx_antennas = int(radar_params.get('txAnt', 3))
        msg.num_rx_antennas = int(radar_params.get('rxAnt', 4))
        msg.num_adc_samples = int(radar_params.get('samples', 256))
        msg.adc_sampling_rate_msps = float(radar_params.get('sampleRate', 12.5))
        
        # Measurement capabilities (example values - would need calculation from config)
        msg.range_resolution = float(0.044)      # meters
        msg.velocity_resolution = float(1.26)    # m/s
        msg.azimuth_resolution = float(0.017)    # radians (~1 degree)
        msg.elevation_resolution = float(0.017)  # radians (~1 degree)
        
        # Maximum ranges (example values)
        msg.max_range = float(9.04)             # meters
        msg.max_velocity = float(20.16)         # m/s
        msg.min_range = float(0.1)              # meters
        msg.min_velocity = float(0.1)           # m/s
        
        # Field of view (example values)
        msg.azimuth_fov_min = float(-1.57)      # -90 degrees
        msg.azimuth_fov_max = float(1.57)       # +90 degrees
        msg.elevation_fov_min = float(-0.79)    # -45 degrees
        msg.elevation_fov_max = float(0.79)     # +45 degrees
        
        # Signal processing configuration
        msg.clutter_removal_enabled = bool(getattr(self.radar, '_clutter_removal', False))
        msg.multi_object_beamforming = bool(getattr(self.radar, 'mob_enabled', False))
        msg.cfar_threshold = float(15.0)        # Example value
        msg.range_fft_size = int(256)         # Example value
        msg.doppler_fft_size = int(32)        # Example value
        
        # Configuration source
        msg.config_file_path = self.radar_profile if self.radar_profile else "default"
        msg.config_file_content = ""     # Could include full config if needed
        msg.config_timestamp = self.get_clock().now().to_msg()
        
        # Publish the message
        self.radar_info_publisher.publish(msg)
        
        if not self.radar_info_published:
            self.get_logger().info('Published radar configuration info')
            self.radar_info_published = True
        
        self.last_info_publish_time = time.time()
    
    def start_data_thread(self):
        """Start the data acquisition thread."""
        if self.data_thread is None or not self.data_thread.is_alive():
            self.stop_event.clear()
            self.data_thread = threading.Thread(target=self._data_acquisition_loop)
            self.data_thread.daemon = True
            self.data_thread.start()
            self.get_logger().info('Data acquisition thread started')
    
    def _data_acquisition_loop(self):
        """Main data acquisition loop running in separate thread."""
        if not self.radar:
            return
            
        try:
            self.radar.configure_and_start()
            self.is_running = True
            self.get_logger().info('Radar started successfully')
            
            # Publish updated radar info now that streaming started
            self.publish_radar_info()
            
            while not self.stop_event.is_set() and rclpy.ok():
                try:
                    # Get radar data
                    radar_data = RadarData(self.radar)
                    
                    if radar_data and radar_data.pc is not None:
                        # Convert to RadarPointCloud
                        point_cloud = radar_data.to_point_cloud()
                        
                        # Publish the data
                        self.publish_point_cloud(point_cloud, radar_data)
                    
                    # Periodically publish radar info
                    current_time = time.time()
                    if (current_time - self.last_info_publish_time) > (1.0 / self.radar_info_publish_rate):
                        self.publish_radar_info()
                    
                    # Small delay to prevent overwhelming the system
                    time.sleep(0.001)
                    
                except Exception as e:
                    self.get_logger().error(f'Error in data acquisition: {e}')
                    time.sleep(0.1)
                    
        except Exception as e:
            self.get_logger().error(f'Error starting radar: {e}')
        finally:
            self.is_running = False
            if self.radar:
                self.radar.stop()
                self.get_logger().info('Radar stopped')
    
    def publish_point_cloud(self, point_cloud: RadarPointCloud, radar_data: RadarData):
        """
        Publish radar point cloud data.
        
        Args:
            point_cloud: RadarPointCloud object containing the data
            radar_data: Raw radar data object for additional information
        """
        if point_cloud.num_points == 0:
            return
            
        # Create message
        msg = RadarPointCloudMsg()
        
        # Set header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        
        # Set frame information
        msg.frame_number = radar_data.frame_number or 0
        msg.num_points = point_cloud.num_points
        
        # Get Cartesian coordinates
        x, y, z = point_cloud.to_cartesian()
        
        # Set position data
        msg.x = x.tolist()
        msg.y = y.tolist()
        msg.z = z.tolist()
        
        # Set spherical coordinates
        msg.range = point_cloud.range.tolist()
        msg.azimuth = point_cloud.azimuth.tolist()
        msg.elevation = point_cloud.elevation.tolist()
        
        # Set velocity data
        msg.velocity = point_cloud.velocity.tolist()
        
        # Set signal quality metrics
        msg.snr = point_cloud.snr.tolist()
        msg.rcs = point_cloud.rcs.tolist()
        
        # Set additional radar-specific data
        if hasattr(radar_data, 'noise') and radar_data.noise:
            msg.noise = radar_data.noise
        else:
            msg.noise = [0.0] * point_cloud.num_points
            
        # Placeholder values for optional fields
        msg.doppler_bin = [0] * point_cloud.num_points
        msg.intensity = point_cloud.snr.tolist()  # Use SNR as intensity approximation
        
        # Publish the message
        self.point_cloud_publisher.publish(msg)
        
        # Log periodically
        if msg.frame_number % 100 == 0:
            self.get_logger().info(
                f'Published frame {msg.frame_number} with {msg.num_points} points'
            )
    
    def stop_radar(self):
        """Stop the radar and data acquisition."""
        self.get_logger().info('Stopping radar...')
        
        # Stop data acquisition thread
        if self.data_thread and self.data_thread.is_alive():
            self.stop_event.set()
            self.data_thread.join(timeout=5.0)
            
        # Stop and disconnect radar
        if self.radar:
            self.radar.stop()
            self.radar.close()
            self.radar = None
            
        self.is_connected = False
        self.is_running = False
        self.get_logger().info('Radar stopped successfully')
    
    def destroy_node(self):
        """Clean up resources when node is destroyed."""
        self.stop_radar()
        super().destroy_node()


def main(args=None):
    """Main function to run the radar publisher node."""
    rclpy.init(args=args)
    
    try:
        node = RadarPublisherNode()
        
        # Use executor for better performance
        executor = rclpy.executors.SingleThreadedExecutor()
        executor.add_node(node)
        
        try:
            executor.spin()
        except KeyboardInterrupt:
            node.get_logger().info('Keyboard interrupt received, shutting down...')
        finally:
            node.destroy_node()
            
    except Exception as e:
        logger.error(f'Error running radar publisher node: {e}')
        import traceback
        logger.error(f'Full traceback: {traceback.format_exc()}')
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main() 