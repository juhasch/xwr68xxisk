"""Record radar data from the sensor and save it to a file."""

import os
import time
import numpy as np
from typing import Tuple, List, Optional, Dict, Any, Literal
from datetime import datetime
import pypcd
from dataclasses import dataclass, field

from xwr68xxisk.radar import RadarConnection, create_radar, RadarConnectionError
from xwr68xxisk.parse import RadarData
from xwr68xxisk.point_cloud import RadarPointCloud

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
                 buffer_in_memory: bool = True):
        """
        Initialize the recorder.
        
        Args:
            base_filename: Base filename without extension
            format_type: Type of file format to save ('csv' or 'pcd')
            buffer_in_memory: Whether to buffer frames in memory before saving
                            (required for PCD format, optional for CSV)
                            
        Raises:
            TypeError: If format_type is not one of the supported formats
        """
        if format_type not in ['csv', 'pcd']:
            raise TypeError(f"Unsupported format type: {format_type}. Must be one of: csv, pcd")
            
        self.base_filename = base_filename
        self.format_type = format_type
        self.buffer_in_memory = buffer_in_memory or format_type == 'pcd'
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(base_filename), exist_ok=True)
        
        # Initialize storage
        self.frames: List[PointCloudFrame] = []
        self.csv_file = None
        self.total_points = 0
        self.frame_count = 0
        
        # Open file if not buffering in memory
        if not self.buffer_in_memory:
            if format_type == 'csv':
                self.csv_file = open(f"{base_filename}.csv", 'w')
                self._write_csv_header()
    
    def _write_csv_header(self):
        """Write the CSV header."""
        self.csv_file.write("timestamp_ns,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs\n")
    
    def add_frame(self, point_cloud: RadarPointCloud, frame_number: int) -> None:
        """
        Add a new frame of point cloud data.
        
        Args:
            point_cloud: RadarPointCloud object containing the frame data
            frame_number: Frame number
        """
        frame = PointCloudFrame(
            timestamp_ns=time.time_ns(),
            frame_number=frame_number,
            points=point_cloud
        )
        
        if self.buffer_in_memory:
            self.frames.append(frame)
        else:
            self._write_frame_csv(frame)
        
        self.total_points += point_cloud.num_points
        self.frame_count += 1
    
    def _write_frame_csv(self, frame: PointCloudFrame) -> None:
        """
        Write a single frame to CSV file.
        
        Args:
            frame: PointCloudFrame object containing the frame data
        """
        x, y, z = frame.points.to_cartesian()
        
        for i in range(frame.points.num_points):
            self.csv_file.write(
                f"{frame.timestamp_ns},{frame.frame_number},{x[i]:.3f},{y[i]:.3f},{z[i]:.3f},"
                f"{frame.points.velocity[i]:.3f},{frame.points.range[i]:.3f},"
                f"{frame.points.azimuth[i]:.3f},{frame.points.elevation[i]:.3f},"
                f"{frame.points.snr[i]:.3f},{frame.points.rcs[i]:.3f}\n"
            )
        self.csv_file.flush()
    
    def _save_to_pcd(self) -> None:
        """Save all buffered frames to a PCD file."""
        if not self.frames:
            return
            
        # Calculate total number of points
        total_points = sum(frame.points.num_points for frame in self.frames)
        
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
            x, y, z = frame.points.to_cartesian()
            points_in_frame = frame.points.num_points
            
            # Fill in the data for this frame
            data['x'][current_idx:current_idx + points_in_frame] = x
            data['y'][current_idx:current_idx + points_in_frame] = y
            data['z'][current_idx:current_idx + points_in_frame] = z
            data['velocity'][current_idx:current_idx + points_in_frame] = frame.points.velocity
            data['range'][current_idx:current_idx + points_in_frame] = frame.points.range
            data['azimuth'][current_idx:current_idx + points_in_frame] = frame.points.azimuth
            data['elevation'][current_idx:current_idx + points_in_frame] = frame.points.elevation
            data['snr'][current_idx:current_idx + points_in_frame] = frame.points.snr
            data['rcs'][current_idx:current_idx + points_in_frame] = frame.points.rcs
            data['timestamp_ns'][current_idx:current_idx + points_in_frame] = frame.timestamp_ns
            data['frame'][current_idx:current_idx + points_in_frame] = frame.frame_number
            
            current_idx += points_in_frame
        
        # Create and save PCD file
        pc = pypcd.PointCloud.from_array(data)
        pc.save_pcd(f"{self.base_filename}.pcd", compression='binary_compressed')
    
    def save(self) -> None:
        """Save the recorded data to file(s)."""
        if self.buffer_in_memory:
            if self.format_type == 'csv':
                with open(f"{self.base_filename}.csv", 'w') as f:
                    # Write header
                    f.write("timestamp_ns,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs\n")
                    # Write frames
                    for frame in self.frames:
                        x, y, z = frame.points.to_cartesian()
                        for i in range(frame.points.num_points):
                            f.write(
                                f"{frame.timestamp_ns},{frame.frame_number},{x[i]:.3f},{y[i]:.3f},{z[i]:.3f},"
                                f"{frame.points.velocity[i]:.3f},{frame.points.range[i]:.3f},"
                                f"{frame.points.azimuth[i]:.3f},{frame.points.elevation[i]:.3f},"
                                f"{frame.points.snr[i]:.3f},{frame.points.rcs[i]:.3f}\n"
                            )
            elif self.format_type == 'pcd':
                self._save_to_pcd()
    
    def close(self) -> None:
        """Close the recorder and save any buffered data."""
        if self.buffer_in_memory:
            self.save()
        elif self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None


def main(serial_number: Optional[str] = None):
    # Create recordings directory if it doesn't exist
    recording_dir = "recordings"
    os.makedirs(recording_dir, exist_ok=True)

    # Create base filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = os.path.join(recording_dir, f"radar_data_{timestamp}")
    
    # Create recorders for different formats
    csv_recorder = PointCloudRecorder(base_filename, 'csv', buffer_in_memory=False)
    pcd_recorder = PointCloudRecorder(base_filename, 'pcd')  # PCD requires buffering
      
    print("Starting radar")

    radar_base = RadarConnection()
    radar_type, config_file = radar_base.detect_radar_type()
    if not radar_type:
        raise RadarConnectionError("No supported radar detected")
    
    print(f"Creating {radar_type} radar instance")
    radar = create_radar(radar_type)            
    radar.connect(config_file)

    if radar.version_info:
        formatted_info = '\n'.join(str(line) for line in radar.version_info)
        print(formatted_info)

    radar.configure_and_start()

    try:
        print(f"Recording data to {base_filename}.[csv,pcd]")
        print("Press Ctrl+C to stop recording")
        
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
                print(f"\rFrame: {frame_number}, Points: {point_cloud.num_points}, "
                      f"Total: {csv_recorder.total_points}, "
                      f"Rate: {points_per_second:.1f} pts/s    ", end="", flush=True)
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
                    print("\nNo data received from radar for too long. Please check the connection and configuration.")
                    break
                
            time.sleep(0.1)  # Wait a bit longer when no data is received
                    
    except KeyboardInterrupt:
        print("\nRecording stopped by user")
    finally:
        # Close recorders and radar
        csv_recorder.close()
        pcd_recorder.close()
        radar.close()
        
        # Print final statistics
        elapsed_time = time.time() - start_time
        print("\nRecording completed:")
        print(f"Total frames: {frame_count}")
        print(f"Total points: {csv_recorder.total_points}")
        print(f"Average points per frame: {csv_recorder.total_points/frame_count:.1f}" if frame_count > 0 else "No frames recorded")
        print(f"Average points per second: {csv_recorder.total_points/elapsed_time:.1f}" if elapsed_time > 0 else "No time elapsed")
        print(f"Data saved to:")
        print(f"  - {base_filename}.csv")
        print(f"  - {base_filename}.pcd")

if __name__ == "__main__":
    main() 