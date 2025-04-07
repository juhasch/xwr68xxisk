"""IMU data recorder.

This module provides functionality to record IMU data to CSV files. The IMU data includes
orientation (yaw, pitch, roll) and acceleration (x, y, z) values, along with motion intent
and request flags.
"""

import os
import time
import csv
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .imu import IMU

logger = logging.getLogger(__name__)

@dataclass
class IMUFrame:
    """Class to store a single frame of IMU data."""
    timestamp_ns: int
    frame_number: int
    data: Dict[str, Any]

class IMURecorder:
    """Class to handle recording IMU data to CSV files."""
    
    def __init__(self, base_filename: str, buffer_in_memory: bool = True):
        """Initialize the IMU recorder.
        
        Args:
            base_filename: Base filename without extension
            buffer_in_memory: Whether to buffer frames in memory before saving
        """
        self.base_filename = base_filename
        self.buffer_in_memory = buffer_in_memory
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(base_filename), exist_ok=True)
        
        # Initialize storage
        self.frames: List[IMUFrame] = []
        self.csv_file = None
        self.frame_count = 0
        
        # Open file if not buffering in memory
        if not self.buffer_in_memory:
            self.csv_file = open(f"{base_filename}.csv", 'w', newline='')
            self._write_csv_header()
    
    def _write_csv_header(self):
        """Write the CSV header."""
        fieldnames = [
            'timestamp_ns', 'frame', 'index',
            'yaw', 'pitch', 'roll',
            'x_acceleration', 'y_acceleration', 'z_acceleration',
            'motion_intent', 'motion_request'
        ]
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()

    def add_frame(self, imu_data: Dict[str, Any]) -> None:
        """Add a new frame of IMU data.
        
        Args:
            imu_data: Dictionary containing IMU measurements
        """
        frame = IMUFrame(
            timestamp_ns=time.time_ns(),
            frame_number=self.frame_count,
            data=imu_data
        )
        
        if self.buffer_in_memory:
            self.frames.append(frame)
        else:
            self._write_frame_csv(frame)
        
        self.frame_count += 1
    
    def _write_frame_csv(self, frame: IMUFrame) -> None:
        """Write a single frame to CSV file."""
        try:
            row = {
                'timestamp_ns': frame.timestamp_ns,
                'frame': frame.frame_number,
                'index': frame.data['index'],
                'yaw': frame.data['yaw'],
                'pitch': frame.data['pitch'],
                'roll': frame.data['roll'],
                'x_acceleration': frame.data['x_acceleration'],
                'y_acceleration': frame.data['y_acceleration'],
                'z_acceleration': frame.data['z_acceleration'],
                'motion_intent': frame.data['motion_intent'],
                'motion_request': frame.data['motion_request']
            }
            self.csv_writer.writerow(row)
            self.csv_file.flush()
        except Exception as e:
            logger.error(f"Error writing frame to CSV: {e}")
    
    def save(self) -> None:
        """Save the recorded data to file."""
        if not self.buffer_in_memory:
            logger.info("Data already saved (not buffering in memory)")
            return
            
        try:
            with open(f"{self.base_filename}.csv", 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp_ns', 'frame', 'index',
                    'yaw', 'pitch', 'roll',
                    'x_acceleration', 'y_acceleration', 'z_acceleration',
                    'motion_intent', 'motion_request'
                ])
                writer.writeheader()
                
                for frame in self.frames:
                    try:
                        row = {
                            'timestamp_ns': frame.timestamp_ns,
                            'frame': frame.frame_number,
                            'index': frame.data['index'],
                            'yaw': frame.data['yaw'],
                            'pitch': frame.data['pitch'],
                            'roll': frame.data['roll'],
                            'x_acceleration': frame.data['x_acceleration'],
                            'y_acceleration': frame.data['y_acceleration'],
                            'z_acceleration': frame.data['z_acceleration'],
                            'motion_intent': frame.data['motion_intent'],
                            'motion_request': frame.data['motion_request']
                        }
                        writer.writerow(row)
                    except Exception as e:
                        logger.error(f"Error writing frame {frame.frame_number} to CSV: {e}")
                        continue
                        
            logger.info(f"Saved {len(self.frames)} frames to {self.base_filename}.csv")
        except Exception as e:
            logger.error(f"Error saving to CSV file: {e}")
    
    def close(self) -> None:
        """Close the recorder and save any buffered data."""
        try:
            if self.buffer_in_memory:
                self.save()
            elif self.csv_file is not None:
                self.csv_file.close()
                self.csv_file = None
            logger.info(f"Recorder closed. Recorded {self.frame_count} frames.")
        except Exception as e:
            logger.error(f"Error closing recorder: {e}")

def main(port: str = '/dev/ttyUSB0'):
    """Record IMU data to CSV file.
    
    Args:
        port: Serial port for IMU connection
    """
    # Create recordings directory if it doesn't exist
    recording_dir = "recordings"
    os.makedirs(recording_dir, exist_ok=True)

    # Create base filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = os.path.join(recording_dir, f"imu_data_{timestamp}")
    
    # Create recorder
    recorder = IMURecorder(base_filename, buffer_in_memory=False)
    
    print("Starting IMU")
    imu = IMU(port)
    
    try:
        print(f"Recording data to {base_filename}.csv")
        print("Press Ctrl+C to stop recording")
        
        start_time = time.time()
        last_status_update = time.time()
        
        while True:
            # Get next IMU reading
            imu_data = next(imu)
            if imu_data is not None:
                # Add frame to recorder
                recorder.add_frame(imu_data)
                
                # Print status update every second
                current_time = time.time()
                if current_time - last_status_update >= 1.0:
                    elapsed_time = current_time - start_time
                    frames_per_second = recorder.frame_count / elapsed_time if elapsed_time > 0 else 0
                    print(f"\rFrame: {recorder.frame_count}, Rate: {frames_per_second:.1f} Hz    ", end="", flush=True)
                    last_status_update = current_time
            
            time.sleep(0.01)  # 100Hz update rate
            
    except KeyboardInterrupt:
        print("\nRecording stopped by user")
    finally:
        # Close recorder
        recorder.close()
        
        # Print final statistics
        elapsed_time = time.time() - start_time
        print("\nRecording completed:")
        print(f"Total frames: {recorder.frame_count}")
        print(f"Average frames per second: {recorder.frame_count/elapsed_time:.1f}" if elapsed_time > 0 else "No time elapsed")
        print(f"Data saved to: {base_filename}.csv")

if __name__ == "__main__":
    main() 