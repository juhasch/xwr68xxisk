#!/usr/bin/env python3

"""
ROS2 node for replaying recorded mmWave radar data from CSV and YAML files.
This node is useful for testing and development without actual radar hardware.
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSDurabilityPolicy
import pandas as pd
import yaml
import os
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import time
import threading

from std_msgs.msg import Header
from xwr68xxisk.msg import RadarPointCloud, RadarInfo


class RadarReplayNode(Node):
    """ROS2 node for replaying recorded radar data from CSV and YAML files."""
    
    def __init__(self):
        super().__init__('radar_replay_node')
        
        # Declare parameters
        self.declare_parameter('recording_directory', '')
        self.declare_parameter('base_filename', '')
        self.declare_parameter('point_cloud_topic', 'radar_point_cloud')
        self.declare_parameter('radar_info_topic', 'radar_info')
        self.declare_parameter('frame_id', 'radar_link')
        self.declare_parameter('replay_rate_hz', 10.0)
        self.declare_parameter('loop_replay', True)
        self.declare_parameter('use_original_timestamps', False)
        self.declare_parameter('time_scale_factor', 1.0)
        
        # Get parameters
        self.recording_dir = self.get_parameter('recording_directory').get_parameter_value().string_value
        self.base_filename = self.get_parameter('base_filename').get_parameter_value().string_value
        self.point_cloud_topic = self.get_parameter('point_cloud_topic').get_parameter_value().string_value
        self.radar_info_topic = self.get_parameter('radar_info_topic').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.replay_rate = self.get_parameter('replay_rate_hz').get_parameter_value().double_value
        self.loop_replay = self.get_parameter('loop_replay').get_parameter_value().bool_value
        self.use_original_timestamps = self.get_parameter('use_original_timestamps').get_parameter_value().bool_value
        self.time_scale_factor = self.get_parameter('time_scale_factor').get_parameter_value().double_value
        
        # Validate parameters
        if not self.recording_dir or not self.base_filename:
            self.get_logger().error("recording_directory and base_filename parameters are required")
            return
            
        # Setup file paths
        self.metadata_file = os.path.join(self.recording_dir, f"{self.base_filename}_metadata.yaml")
        self.csv_file = os.path.join(self.recording_dir, f"{self.base_filename}.csv")
        
        # Verify files exist
        if not os.path.exists(self.metadata_file):
            self.get_logger().error(f"Metadata file not found: {self.metadata_file}")
            return
        if not os.path.exists(self.csv_file):
            self.get_logger().error(f"CSV file not found: {self.csv_file}")
            return
            
        # Load metadata
        self.metadata = self._load_metadata()
        if not self.metadata:
            return
            
        # Load radar configuration
        self.radar_config = self._load_radar_config()
        
        # Load CSV data
        self.df = self._load_csv_data()
        if self.df is None:
            return
            
        # Setup QoS profiles
        point_cloud_qos = QoSProfile(
            depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE
        )
        
        radar_info_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL  # Latched behavior
        )
        
        # Create publishers
        self.point_cloud_pub = self.create_publisher(
            RadarPointCloud, 
            self.point_cloud_topic, 
            point_cloud_qos
        )
        
        self.radar_info_pub = self.create_publisher(
            RadarInfo, 
            self.radar_info_topic, 
            radar_info_qos
        )
        
        # Initialize replay state
        self.current_frame = 0
        self.frames = self.df['frame'].unique()
        self.total_frames = len(self.frames)
        self.start_time = None
        self.is_replaying = False
        
        # Start replay thread
        self.replay_thread = threading.Thread(target=self._replay_worker, daemon=True)
        self.replay_thread.start()
        
        self.get_logger().info(f"Radar replay node initialized")
        self.get_logger().info(f"Recording: {self.base_filename}")
        self.get_logger().info(f"Total frames: {self.total_frames}")
        self.get_logger().info(f"Replay rate: {self.replay_rate} Hz")
        self.get_logger().info(f"Loop replay: {self.loop_replay}")
        
    def _load_metadata(self) -> Optional[Dict[str, Any]]:
        """Load metadata from YAML file."""
        try:
            with open(self.metadata_file, 'r') as f:
                metadata = yaml.safe_load(f)
            self.get_logger().info(f"Loaded metadata: {metadata['recording'].get('total_frames', 'unknown')} frames, {metadata['recording'].get('total_points', 'unknown')} total points")
            return metadata
        except Exception as e:
            self.get_logger().error(f"Failed to load metadata: {e}")
            return None
            
    def _load_radar_config(self) -> Dict[str, Any]:
        """Load radar configuration from .cfg file."""
        config = {}
        
        if 'radar_config_file' in self.metadata:
            config_file = os.path.join(self.recording_dir, self.metadata['radar_config_file'])
            if os.path.exists(config_file):
                try:
                    # Parse the configuration file
                    config = self._parse_radar_config_file(config_file)
                    self.get_logger().info(f"Loaded radar config from: {config_file}")
                except Exception as e:
                    self.get_logger().warning(f"Failed to parse radar config: {e}")
            else:
                self.get_logger().warning(f"Radar config file not found: {config_file}")
                
        return config
        
    def _parse_radar_config_file(self, config_file: str) -> Dict[str, Any]:
        """Parse radar configuration file and extract key parameters."""
        config = {}
        
        with open(config_file, 'r') as f:
            lines = f.readlines()
            
        # Extract values from comment lines
        for line in lines:
            line = line.strip()
            if line.startswith('% Range resolution') and 'm' in line:
                try:
                    config['range_resolution'] = float(line.split()[-1])
                except:
                    pass
            elif line.startswith('% Velocity resolution') and 'm/s' in line:
                try:
                    config['velocity_resolution'] = float(line.split()[-1])
                except:
                    pass
            elif line.startswith('% Max distance') and 'm' in line:
                try:
                    config['max_range'] = float(line.split()[-1])
                except:
                    pass
            elif line.startswith('% Max umambiguous relative velocity') and 'kmph' in line:
                try:
                    # Convert from kmph to m/s
                    config['max_velocity'] = float(line.split()[-1]) / 3.6
                except:
                    pass
            elif line.startswith('% Carrier frequency') and 'GHz' in line:
                try:
                    config['carrier_frequency'] = float(line.split()[-1])
                except:
                    pass
        
        # Set defaults if not found
        config.setdefault('range_resolution', 0.044)
        config.setdefault('velocity_resolution', 1.26)
        config.setdefault('max_range', 9.04)
        config.setdefault('max_velocity', 20.16)
        config.setdefault('carrier_frequency', 60.0)
        
        return config
        
    def _load_csv_data(self) -> Optional[pd.DataFrame]:
        """Load point cloud data from CSV file."""
        try:
            df = pd.read_csv(self.csv_file)
            
            # Verify expected columns exist
            required_columns = ['timestamp', 'frame', 'x', 'y', 'z', 'velocity', 
                              'range', 'azimuth', 'elevation', 'snr', 'rcs']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                self.get_logger().error(f"Missing required columns in CSV: {missing_columns}")
                return None
                
            # Convert timestamp column to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            self.get_logger().info(f"Loaded CSV data: {len(df)} points across {df['frame'].nunique()} frames")
            return df
            
        except Exception as e:
            self.get_logger().error(f"Failed to load CSV data: {e}")
            return None
            
    def _create_radar_info_message(self) -> RadarInfo:
        """Create RadarInfo message with static radar configuration."""
        msg = RadarInfo()
        
        # Header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        
        # Sensor information
        msg.sensor_model = "AWR6843ISK"
        msg.firmware_version = "unknown"
        msg.config_file_path = self.base_filename
        
        # Field of view
        msg.azimuth_fov_min = -1.57  # -90 degrees
        msg.azimuth_fov_max = 1.57   # +90 degrees
        msg.elevation_fov_min = -1.57    # -90 degrees (if available)
        msg.elevation_fov_max = 1.57     # +90 degrees (if available)
        
        # Resolution and range limits
        msg.range_resolution = self.radar_config.get('range_resolution', 0.044)
        msg.velocity_resolution = self.radar_config.get('velocity_resolution', 1.26)
        msg.azimuth_resolution = 0.1  # Approximate
        msg.elevation_resolution = 0.1  # Approximate
        
        msg.min_range = 0.1
        msg.max_range = self.radar_config.get('max_range', 9.04)
        msg.min_velocity = -self.radar_config.get('max_velocity', 20.16)
        msg.max_velocity = self.radar_config.get('max_velocity', 20.16)
        
        # Processing configuration 
        msg.range_fft_size = self.radar_config.get('rangeBins', 256)
        msg.doppler_fft_size = self.radar_config.get('chirpsPerFrame', 64)
        msg.clutter_removal_enabled = True
        msg.multi_object_beamforming = False
        msg.cfar_threshold = 6.0
        
        # Additional radar configuration
        msg.carrier_frequency_ghz = 60.25
        msg.bandwidth_mhz = 1200.0
        msg.frame_period_ms = self.radar_config.get('framePeriod', 100.0)
        msg.num_tx_antennas = 3
        msg.num_rx_antennas = 4
        msg.num_adc_samples = self.radar_config.get('samples', 256)
        msg.adc_sampling_rate_msps = 5.0
            
        return msg
        
    def _create_point_cloud_message(self, frame_data: pd.DataFrame) -> RadarPointCloud:
        """Create RadarPointCloud message from frame data."""
        msg = RadarPointCloud()
        
        # Header
        msg.header = Header()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        
        # Frame information
        if len(frame_data) > 0:
            msg.frame_number = int(frame_data['frame'].iloc[0])
        else:
            msg.frame_number = 0
        msg.num_points = len(frame_data)
        
        # Convert data to lists
        msg.x = frame_data['x'].tolist()
        msg.y = frame_data['y'].tolist()
        msg.z = frame_data['z'].tolist()
        msg.range = frame_data['range'].tolist()
        msg.azimuth = frame_data['azimuth'].tolist()
        msg.elevation = frame_data['elevation'].tolist()
        msg.velocity = frame_data['velocity'].tolist()
        msg.snr = frame_data['snr'].tolist()
        msg.rcs = frame_data['rcs'].tolist()
        
        # Initialize optional arrays as empty (can be filled if data is available)
        msg.noise = []
        msg.doppler_bin = []
        msg.intensity = []
        
        return msg
        
    def _replay_worker(self):
        """Worker thread for replaying radar data."""
        self.is_replaying = True
        
        # Publish RadarInfo once at start
        radar_info_msg = self._create_radar_info_message()
        self.radar_info_pub.publish(radar_info_msg)
        self.get_logger().info("Published RadarInfo message")
        
        # Calculate timing
        frame_interval = 1.0 / self.replay_rate
        
        if self.use_original_timestamps and len(self.frames) > 1:
            # Use original timing from timestamps
            frame_times = []
            for frame_num in self.frames:
                frame_data = self.df[self.df['frame'] == frame_num]
                if len(frame_data) > 0:
                    frame_times.append(frame_data['timestamp'].iloc[0])
            
            # Calculate intervals between frames
            intervals = []
            for i in range(1, len(frame_times)):
                interval = (frame_times[i] - frame_times[i-1]).total_seconds()
                intervals.append(interval * self.time_scale_factor)
        
        frame_idx = 0
        while rclpy.ok() and self.is_replaying:
            try:
                if frame_idx >= len(self.frames):
                    if self.loop_replay:
                        frame_idx = 0
                        self.get_logger().info("Looping replay...")
                    else:
                        self.get_logger().info("Replay completed")
                        break
                
                frame_num = self.frames[frame_idx]
                frame_data = self.df[self.df['frame'] == frame_num]
                
                # Create and publish point cloud message
                pc_msg = self._create_point_cloud_message(frame_data)
                self.point_cloud_pub.publish(pc_msg)
                
                self.get_logger().debug(f"Published frame {frame_num} with {len(frame_data)} points")
                
                # Calculate sleep time
                if self.use_original_timestamps and frame_idx < len(intervals):
                    sleep_time = intervals[frame_idx]
                else:
                    sleep_time = frame_interval
                    
                frame_idx += 1
                time.sleep(sleep_time)
                
            except Exception as e:
                self.get_logger().error(f"Error in replay worker: {e}")
                break
                
        self.is_replaying = False
        
    def destroy_node(self):
        """Cleanup when node is destroyed."""
        self.is_replaying = False
        if hasattr(self, 'replay_thread') and self.replay_thread.is_alive():
            self.replay_thread.join(timeout=1.0)
        super().destroy_node()


def main(args=None):
    """Main entry point for the radar replay node."""
    rclpy.init(args=args)
    
    try:
        node = RadarReplayNode()
        
        # Spin until shutdown
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'node' in locals():
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main() 