"""Record radar data from the sensor and save it to a file."""

import os
import time
import logging
import numpy as np
from typing import Tuple, List, Optional, Dict, Any, Literal
from datetime import datetime
import pypcd
from dataclasses import dataclass, field

from xwr68xxisk.radar import RadarConnection, create_radar, RadarConnectionError
from xwr68xxisk.parse import RadarData
from xwr68xxisk.point_cloud import RadarPointCloud
from xwr68xxisk.clustering import Cluster
from xwr68xxisk.tracking import Track
from xwr68xxisk.configs import ConfigManager

# Configure logging
logger = logging.getLogger(__name__)

RUNNER_CI = True if os.getenv("CI") == "true" else False


@dataclass
class PointCloudFrame:
    """Class to store a single frame of point cloud data."""
    timestamp_ns: int
    frame_number: int
    points: RadarPointCloud
    metadata: Dict[str, Any] = field(default_factory=dict)


class PointCloudRecorder:
    """Class to handle recording point cloud data in different formats."""
    
    def __init__(self, 
                 base_filename: str,
                 format_type: Literal['csv', 'pcd'],
                 buffer_in_memory: bool = True,
                 enable_clustering: bool = False,
                 enable_tracking: bool = False,
                 clustering_params: Optional[Dict] = None,
                 tracking_params: Optional[Dict] = None):
        """
        Initialize the recorder.
        
        Args:
            base_filename: Base filename without extension
            format_type: Type of file format to save ('csv' or 'pcd')
            buffer_in_memory: Whether to buffer frames in memory before saving
            enable_clustering: Whether to perform clustering on point clouds
            enable_tracking: Whether to perform tracking on clusters
            clustering_params: Parameters for clustering algorithm
            tracking_params: Parameters for tracking algorithm
        """
        if format_type not in ['csv', 'pcd']:
            raise TypeError(f"Unsupported format type: {format_type}. Must be one of: csv, pcd")
            
        self.base_filename = base_filename
        self.format_type = format_type
        self.buffer_in_memory = buffer_in_memory or format_type == 'pcd'
        
        # Initialize clustering and tracking if enabled
        self.enable_clustering = enable_clustering
        self.enable_tracking = enable_tracking
        
        if enable_clustering:
            from xwr68xxisk.clustering import PointCloudClustering
            self.clusterer = PointCloudClustering(**(clustering_params or {}))
            
        if enable_tracking:
            if not enable_clustering:
                raise ValueError("Tracking requires clustering to be enabled")
            from xwr68xxisk.tracking import PointCloudTracker
            self.tracker = PointCloudTracker(**(tracking_params or {}))
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(base_filename), exist_ok=True)
        
        # Initialize storage
        self.frames: List[PointCloudFrame] = []
        self.csv_file = None
        self.total_points = 0
        self.frame_count = 0
        
        # Open files if not buffering in memory
        if not self.buffer_in_memory:
            if format_type == 'csv':
                self.csv_file = open(f"{base_filename}.csv", 'w')
                self._write_csv_header()
                
            # Open additional files for clusters and tracks if enabled
            if enable_clustering:
                self.clusters_file = open(f"{base_filename}_clusters.csv", 'w')
                self._write_clusters_header()
                
            if enable_tracking:
                self.tracks_file = open(f"{base_filename}_tracks.csv", 'w')
                self._write_tracks_header()
    
    def _write_csv_header(self):
        """Write the CSV header."""
        self.csv_file.write("timestamp_ns,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs\n")
        
    def _write_clusters_header(self):
        """Write the clusters CSV header."""
        self.clusters_file.write("timestamp_ns,frame,cluster_id,x,y,z,velocity,size_x,size_y,size_z,num_points\n")
        
    def _write_tracks_header(self):
        """Write the tracks CSV header."""
        self.tracks_file.write("timestamp_ns,frame,track_id,x,y,z,vx,vy,vz,age,hits\n")

    def add_frame(self, point_cloud: RadarPointCloud, frame_number: int) -> None:
        """
        Add a new frame of point cloud data.
        
        Args:
            point_cloud: RadarPointCloud object containing the frame data
            frame_number: Frame number
        """
        # Skip empty point clouds
        if point_cloud.num_points == 0:
            return
            
        # Create frame object
        frame = PointCloudFrame(
            timestamp_ns=time.time_ns(),
            frame_number=frame_number,
            points=point_cloud
        )
        
        # Perform clustering if enabled
        clusters = []
        tracks = []
        if self.enable_clustering:
            try:
                clusters = self.clusterer.cluster(point_cloud)
                frame.metadata['clusters'] = clusters
                
                # Perform tracking if enabled
                if self.enable_tracking:
                    tracks = self.tracker.update(clusters)
                    frame.metadata['tracks'] = tracks
            except Exception as e:
                logger.error(f"Error during clustering/tracking: {e}")
        
        if self.buffer_in_memory:
            self.frames.append(frame)
        else:
            try:
                self._write_frame_csv(frame)
                if clusters:
                    self._write_clusters_csv(frame.timestamp_ns, frame_number, clusters)
                if tracks:
                    self._write_tracks_csv(frame.timestamp_ns, frame_number, tracks)
            except Exception as e:
                logger.error(f"Error writing frame to CSV: {e}")
        
        self.total_points += point_cloud.num_points
        self.frame_count += 1
    
    def _write_frame_csv(self, frame: PointCloudFrame) -> None:
        """Write a single frame to CSV file."""
        try:
            x, y, z = frame.points.to_cartesian()
            
            # Ensure all required arrays exist and have the same length
            num_points = frame.points.num_points
            
            # Check if all required attributes exist
            if not hasattr(frame.points, 'velocity') or len(frame.points.velocity) == 0:
                frame.points.velocity = np.zeros(num_points)
            if not hasattr(frame.points, 'range') or len(frame.points.range) == 0:
                frame.points.range = np.zeros(num_points)
            if not hasattr(frame.points, 'azimuth') or len(frame.points.azimuth) == 0:
                frame.points.azimuth = np.zeros(num_points)
            if not hasattr(frame.points, 'elevation') or len(frame.points.elevation) == 0:
                frame.points.elevation = np.zeros(num_points)
            if not hasattr(frame.points, 'snr') or len(frame.points.snr) == 0:
                frame.points.snr = np.zeros(num_points)
            if not hasattr(frame.points, 'rcs') or len(frame.points.rcs) == 0:
                frame.points.rcs = np.zeros(num_points)
            
            # Ensure all arrays have the same length
            min_length = min(
                len(x), len(y), len(z),
                len(frame.points.velocity),
                len(frame.points.range),
                len(frame.points.azimuth),
                len(frame.points.elevation),
                len(frame.points.snr),
                len(frame.points.rcs)
            )
            
            for i in range(min_length):
                self.csv_file.write(
                    f"{frame.timestamp_ns},{frame.frame_number},{x[i]:.3f},{y[i]:.3f},{z[i]:.3f},"
                    f"{frame.points.velocity[i]:.3f},{frame.points.range[i]:.3f},"
                    f"{frame.points.azimuth[i]:.3f},{frame.points.elevation[i]:.3f},"
                    f"{frame.points.snr[i]:.3f},{frame.points.rcs[i]:.3f}\n"
                )
            self.csv_file.flush()
        except Exception as e:
            logger.error(f"Error in _write_frame_csv: {e}")
            # Continue without crashing
        
    def _write_clusters_csv(self, timestamp_ns: int, frame_number: int, clusters: List[Cluster]) -> None:
        """Write clusters to CSV file."""
        try:
            if not clusters:
                return
                
            for i, cluster in enumerate(clusters):
                try:
                    self.clusters_file.write(
                        f"{timestamp_ns},{frame_number},{i},"
                        f"{cluster.centroid[0]:.3f},{cluster.centroid[1]:.3f},{cluster.centroid[2]:.3f},"
                        f"{cluster.velocity:.3f},"
                        f"{cluster.size[0]:.3f},{cluster.size[1]:.3f},{cluster.size[2]:.3f},"
                        f"{cluster.num_points}\n"
                    )
                except Exception as e:
                    logger.error(f"Error writing cluster {i}: {e}")
                    continue
            self.clusters_file.flush()
        except Exception as e:
            logger.error(f"Error in _write_clusters_csv: {e}")
        
    def _write_tracks_csv(self, timestamp_ns: int, frame_number: int, tracks: List[Track]) -> None:
        """Write tracks to CSV file."""
        try:
            if not tracks:
                return
                
            for track in tracks:
                try:
                    self.tracks_file.write(
                        f"{timestamp_ns},{frame_number},{track.track_id},"
                        f"{track.state[0]:.3f},{track.state[1]:.3f},{track.state[2]:.3f},"
                        f"{track.state[3]:.3f},{track.state[4]:.3f},{track.state[5]:.3f},"
                        f"{track.age},{track.hits}\n"
                    )
                except Exception as e:
                    logger.error(f"Error writing track {track.track_id}: {e}")
                    continue
            self.tracks_file.flush()
        except Exception as e:
            logger.error(f"Error in _write_tracks_csv: {e}")

    def _save_to_pcd(self) -> None:
        """Save all buffered frames to a PCD file."""
        if not self.frames:
            logger.warning("No frames to save to PCD file")
            return
            
        try:
            # Calculate total number of points
            total_points = sum(frame.points.num_points for frame in self.frames)
            
            if total_points == 0:
                logger.warning("No points to save to PCD file")
                return
                
            # Create structured array for all points
            dtype = np.dtype([
                ('x', np.float32),
                ('y', np.float32),
                ('z', np.float32),
                ('velocity', np.float32),
                ('range', np.float32),
                ('azimuth', np.float32),
                ('elevation', np.float32),
                ('snr', np.float32),
                ('rcs', np.float32),
                ('timestamp_ns', np.int64),
                ('frame', np.int32)
            ])
            
            data = np.zeros(total_points, dtype=dtype)
            current_idx = 0
            
            # Fill the array with all points
            for frame in self.frames:
                if frame.points.num_points == 0:
                    continue
                    
                try:
                    x, y, z = frame.points.to_cartesian()
                    points_in_frame = frame.points.num_points
                    
                    # Ensure all required attributes exist
                    if not hasattr(frame.points, 'velocity') or len(frame.points.velocity) == 0:
                        frame.points.velocity = np.zeros(points_in_frame)
                    if not hasattr(frame.points, 'range') or len(frame.points.range) == 0:
                        frame.points.range = np.zeros(points_in_frame)
                    if not hasattr(frame.points, 'azimuth') or len(frame.points.azimuth) == 0:
                        frame.points.azimuth = np.zeros(points_in_frame)
                    if not hasattr(frame.points, 'elevation') or len(frame.points.elevation) == 0:
                        frame.points.elevation = np.zeros(points_in_frame)
                    if not hasattr(frame.points, 'snr') or len(frame.points.snr) == 0:
                        frame.points.snr = np.zeros(points_in_frame)
                    if not hasattr(frame.points, 'rcs') or len(frame.points.rcs) == 0:
                        frame.points.rcs = np.zeros(points_in_frame)
                    
                    # Ensure all arrays have the same length
                    min_length = min(
                        len(x), len(y), len(z),
                        len(frame.points.velocity),
                        len(frame.points.range),
                        len(frame.points.azimuth),
                        len(frame.points.elevation),
                        len(frame.points.snr),
                        len(frame.points.rcs)
                    )
                    
                    if min_length == 0:
                        continue
                    
                    # Fill in the data for this frame
                    data['x'][current_idx:current_idx + min_length] = x[:min_length]
                    data['y'][current_idx:current_idx + min_length] = y[:min_length]
                    data['z'][current_idx:current_idx + min_length] = z[:min_length]
                    data['velocity'][current_idx:current_idx + min_length] = frame.points.velocity[:min_length]
                    data['range'][current_idx:current_idx + min_length] = frame.points.range[:min_length]
                    data['azimuth'][current_idx:current_idx + min_length] = frame.points.azimuth[:min_length]
                    data['elevation'][current_idx:current_idx + min_length] = frame.points.elevation[:min_length]
                    data['snr'][current_idx:current_idx + min_length] = frame.points.snr[:min_length]
                    data['rcs'][current_idx:current_idx + min_length] = frame.points.rcs[:min_length]
                    data['timestamp_ns'][current_idx:current_idx + min_length] = frame.timestamp_ns
                    data['frame'][current_idx:current_idx + min_length] = frame.frame_number
                    
                    current_idx += min_length
                except Exception as e:
                    logger.error(f"Error processing frame for PCD: {e}")
                    continue
            
            # Resize the array if we didn't fill it completely
            if current_idx < total_points:
                data = data[:current_idx]
            
            if len(data) == 0:
                logger.warning("No valid points to save to PCD file")
                return
                
            # Create and save PCD file
            pc = pypcd.PointCloud.from_array(data)
            pc.save_pcd(f"{self.base_filename}.pcd", compression='binary_compressed')
            logger.info(f"Saved {len(data)} points to {self.base_filename}.pcd")
        except Exception as e:
            logger.error(f"Error saving to PCD file: {e}")
            # Continue without crashing
    
    def save(self) -> None:
        """Save the recorded data to file(s)."""
        if not self.buffer_in_memory:
            logger.warning("Data already saved (not buffering in memory)")
            return
            
        try:
            # Save point cloud data
            if self.format_type == 'csv':
                try:
                    with open(f"{self.base_filename}.csv", 'w') as f:
                        f.write("timestamp_ns,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs\n")
                        for frame in self.frames:
                            if frame.points.num_points == 0:
                                continue
                                
                            try:
                                x, y, z = frame.points.to_cartesian()
                                
                                # Ensure all required attributes exist
                                num_points = frame.points.num_points
                                if not hasattr(frame.points, 'velocity') or len(frame.points.velocity) == 0:
                                    frame.points.velocity = np.zeros(num_points)
                                if not hasattr(frame.points, 'range') or len(frame.points.range) == 0:
                                    frame.points.range = np.zeros(num_points)
                                if not hasattr(frame.points, 'azimuth') or len(frame.points.azimuth) == 0:
                                    frame.points.azimuth = np.zeros(num_points)
                                if not hasattr(frame.points, 'elevation') or len(frame.points.elevation) == 0:
                                    frame.points.elevation = np.zeros(num_points)
                                if not hasattr(frame.points, 'snr') or len(frame.points.snr) == 0:
                                    frame.points.snr = np.zeros(num_points)
                                if not hasattr(frame.points, 'rcs') or len(frame.points.rcs) == 0:
                                    frame.points.rcs = np.zeros(num_points)
                                
                                # Ensure all arrays have the same length
                                min_length = min(
                                    len(x), len(y), len(z),
                                    len(frame.points.velocity),
                                    len(frame.points.range),
                                    len(frame.points.azimuth),
                                    len(frame.points.elevation),
                                    len(frame.points.snr),
                                    len(frame.points.rcs)
                                )
                                
                                for i in range(min_length):
                                    f.write(
                                        f"{frame.timestamp_ns},{frame.frame_number},{x[i]:.3f},{y[i]:.3f},{z[i]:.3f},"
                                        f"{frame.points.velocity[i]:.3f},{frame.points.range[i]:.3f},"
                                        f"{frame.points.azimuth[i]:.3f},{frame.points.elevation[i]:.3f},"
                                        f"{frame.points.snr[i]:.3f},{frame.points.rcs[i]:.3f}\n"
                                    )
                            except Exception as e:
                                logger.error(f"Error writing frame to CSV: {e}")
                                continue
                    logger.info(f"Saved {len(self.frames)} frames to {self.base_filename}.csv")
                except Exception as e:
                    logger.error(f"Error saving to CSV file: {e}")
            elif self.format_type == 'pcd':
                self._save_to_pcd()
            
            # Save clusters and tracks if enabled
            if self.enable_clustering:
                try:
                    with open(f"{self.base_filename}_clusters.csv", 'w') as f:
                        f.write("timestamp_ns,frame,cluster_id,x,y,z,velocity,size_x,size_y,size_z,num_points\n")
                        for frame in self.frames:
                            if 'clusters' in frame.metadata and frame.metadata['clusters']:
                                try:
                                    self._write_clusters_csv(frame.timestamp_ns, frame.frame_number, frame.metadata['clusters'])
                                except Exception as e:
                                    logger.error(f"Error writing clusters for frame {frame.frame_number}: {e}")
                    logger.info(f"Saved clusters to {self.base_filename}_clusters.csv")
                except Exception as e:
                    logger.error(f"Error saving clusters file: {e}")
                            
            if self.enable_tracking:
                try:
                    with open(f"{self.base_filename}_tracks.csv", 'w') as f:
                        f.write("timestamp_ns,frame,track_id,x,y,z,vx,vy,vz,age,hits\n")
                        for frame in self.frames:
                            if 'tracks' in frame.metadata and frame.metadata['tracks']:
                                try:
                                    self._write_tracks_csv(frame.timestamp_ns, frame.frame_number, frame.metadata['tracks'])
                                except Exception as e:
                                    logger.error(f"Error writing tracks for frame {frame.frame_number}: {e}")
                    logger.info(f"Saved tracks to {self.base_filename}_tracks.csv")
                except Exception as e:
                    logger.error(f"Error saving tracks file: {e}")
        except Exception as e:
            logger.error(f"Error in save method: {e}")
    
    def close(self) -> None:
        """Close the recorder and save any buffered data."""
        try:
            if self.buffer_in_memory:
                self.save()
            else:
                if self.csv_file is not None:
                    self.csv_file.close()
                    self.csv_file = None
                if hasattr(self, 'clusters_file') and self.clusters_file is not None:
                    self.clusters_file.close()
                    self.clusters_file = None
                if hasattr(self, 'tracks_file') and self.tracks_file is not None:
                    self.tracks_file.close()
                    self.tracks_file = None
            logger.info(f"Recorder closed. Recorded {self.frame_count} frames with {self.total_points} points.")
        except Exception as e:
            logger.error(f"Error closing recorder: {e}")


def main(serial_number: Optional[str] = None, profile: str = os.path.join('configs', 'user_profile.cfg')):
    """Record radar data from the sensor.
    
    Args:
        serial_number: Optional serial number of the radar
        profile: Path to the radar profile configuration file
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.load_config()

    # Check if profile exists
    if not os.path.exists(profile):
        logger.error(f"Profile file not found: {profile}")
        raise FileNotFoundError(f"Profile file not found: {profile}")

    # Create recordings directory if it doesn't exist
    recording_dir = "recordings"
    os.makedirs(recording_dir, exist_ok=True)

    # Create base filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = os.path.join(recording_dir, f"radar_data_{timestamp}")
    
    # Get clustering and tracking configuration
    clustering_enabled = config.clustering.enabled
    tracking_enabled = config.tracking.enabled
    
    # Only create clustering params if enabled
    clustering_params = None
    if clustering_enabled:
        clustering_params = {
            'eps': config.clustering.eps,
            'min_samples': config.clustering.min_samples
        }
    
    # Only create tracking params if both clustering and tracking are enabled
    tracking_params = None
    if clustering_enabled and tracking_enabled:
        tracking_params = {
            'dt': config.tracking.dt,
            'max_distance': config.tracking.max_distance,
            'min_hits': config.tracking.min_hits,
            'max_misses': config.tracking.max_misses
        }
    
    # Create recorders for different formats
    csv_recorder = PointCloudRecorder(
        base_filename, 
        'csv',
        buffer_in_memory=False,
        enable_clustering=clustering_enabled,
        enable_tracking=tracking_enabled,
        clustering_params=clustering_params,
        tracking_params=tracking_params
    )
    
    pcd_recorder = PointCloudRecorder(
        base_filename,
        'pcd',
        enable_clustering=clustering_enabled,
        enable_tracking=tracking_enabled,
        clustering_params=clustering_params,
        tracking_params=tracking_params
    )
      
    logger.info("Starting radar")
    if clustering_enabled:
        logger.info("Clustering enabled with parameters: " + str(config.clustering))
    if tracking_enabled:
        logger.info("Tracking enabled with parameters: " + str(config.tracking))

    radar_base = RadarConnection()
    radar_type = radar_base.detect_radar_type()
    if not radar_type:
        logger.error("No supported radar detected")
        raise RadarConnectionError("No supported radar detected")
    
    logger.info(f"Creating {radar_type} radar instance")
    radar = create_radar()
    
    # Connect using the specified profile
    logger.info(f"Using radar profile: {profile}")
    radar.connect(profile)

    if radar.version_info:
        formatted_info = '\n'.join(str(line) for line in radar.version_info)
        logger.info(f"Radar version info:\n{formatted_info}")

    radar.configure_and_start()

    try:
        logger.info(f"Recording data to {base_filename}.[csv,pcd]")
        logger.info("Press Ctrl+C to stop recording")
        
        frame_count = 0
        no_data_count = 0
        max_no_data = 10  # Maximum number of consecutive frames with no data
        start_time = time.time()
        last_status_update = time.time()
        
        while True:
            # Check for data with a short timeout
            data = RadarData(radar)
            
            if data is not None and data.pc is not None:
                # Convert to point cloud
                point_cloud = data.to_point_cloud()
                frame_number = point_cloud.metadata.get('frame_number', frame_count)
                
                # Add frame to both recorders
                csv_recorder.add_frame(point_cloud, frame_number)
                pcd_recorder.add_frame(point_cloud, frame_number)
                
                # Update statistics for display
                elapsed_time = time.time() - start_time
                points_per_second = csv_recorder.total_points / elapsed_time if elapsed_time > 0 else 0
                
                # Print status update (overwrite previous line)
                status_msg = f"\rFrame: {frame_number}, Points: {point_cloud.num_points}, " \
                           f"Total: {csv_recorder.total_points}, " \
                           f"Rate: {points_per_second:.1f} pts/s"
                if clustering_enabled:
                    clusters = point_cloud.metadata.get('clusters', [])
                    status_msg += f", Clusters: {len(clusters)}"
                if tracking_enabled:
                    tracks = point_cloud.metadata.get('tracks', [])
                    status_msg += f", Tracks: {len(tracks)}"
                print(status_msg + "    ", end="", flush=True)
                
                last_status_update = time.time()
                
                frame_count += 1
                no_data_count = 0  # Reset no data counter on successful frame
            else:
                no_data_count += 1
                current_time = time.time()
                
                # Update status message every second
                if current_time - last_status_update >= 1.0:
                    print("\rWaiting for data...", end="", flush=True)
                    last_status_update = current_time
                
                if no_data_count >= max_no_data:
                    logger.error("No data received from radar for too long. Please check the connection and configuration.")
                    break
                
            time.sleep(0.1)  # Wait a bit longer when no data is received
                    
    except KeyboardInterrupt:
        logger.info("\nRecording stopped by user")
    finally:
        # Close recorders and radar
        csv_recorder.close()
        pcd_recorder.close()
        radar.close()
        
        # Print final statistics
        elapsed_time = time.time() - start_time
        logger.info("\nRecording completed:")
        logger.info(f"Total frames: {frame_count}")
        logger.info(f"Total points: {csv_recorder.total_points}")
        logger.info(f"Average points per frame: {csv_recorder.total_points/frame_count:.1f}" if frame_count > 0 else "No frames recorded")
        logger.info(f"Average points per second: {csv_recorder.total_points/elapsed_time:.1f}" if elapsed_time > 0 else "No time elapsed")
        logger.info(f"Data saved to:")
        logger.info(f"  - {base_filename}.csv")
        logger.info(f"  - {base_filename}.pcd")
        if clustering_enabled:
            logger.info(f"  - {base_filename}_clusters.csv")
        if tracking_enabled:
            logger.info(f"  - {base_filename}_tracks.csv")

if __name__ == "__main__":
    main() 