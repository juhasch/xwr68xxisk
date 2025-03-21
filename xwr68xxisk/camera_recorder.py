"""Camera recorder for synchronized multi-camera recording.

This module provides functionality to record video from multiple cameras while maintaining
precise timestamp synchronization. The recordings are stored as:
1. Video files (MP4) for each camera
2. CSV files containing frame timestamps and metadata
3. Optional synchronization file for radar data timestamps
"""

import os
import csv
import time
import cv2
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from threading import Thread, Event, Lock
from queue import Queue
import logging

from .cameras import BaseCamera

logger = logging.getLogger(__name__)

@dataclass
class CameraFrame:
    """Class to store a single frame of camera data with metadata."""
    timestamp: float
    frame_number: int
    camera_id: str
    image: np.ndarray
    metadata: Dict[str, Any]

class CameraRecorder:
    """Class to handle synchronized recording from multiple cameras."""
    
    def __init__(self, base_path: str, cameras: Dict[str, BaseCamera]):
        """Initialize the camera recorder.
        
        Args:
            base_path: Base path for storing recordings
            cameras: Dictionary of camera_id -> camera object pairs
        """
        self.base_path = base_path
        self.cameras = cameras
        self.is_recording = False
        
        # Create recording directory
        os.makedirs(base_path, exist_ok=True)
        
        # Initialize video writers and CSV files for each camera
        self.video_writers: Dict[str, cv2.VideoWriter] = {}
        self.csv_files: Dict[str, Any] = {}
        self.csv_writers: Dict[str, csv.DictWriter] = {}
        
        # Frame counters for each camera
        self.frame_counts: Dict[str, int] = {cam_id: 0 for cam_id in cameras}
        
        # Threading components
        self.frame_queues: Dict[str, Queue] = {cam_id: Queue(maxsize=30) for cam_id in cameras}
        self.stop_event = Event()
        self.recording_threads: Dict[str, Thread] = {}
        self.queue_locks: Dict[str, Lock] = {cam_id: Lock() for cam_id in cameras}
        
    def start(self):
        """Start recording from all cameras."""
        if self.is_recording:
            logger.warning("Recording is already in progress")
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        try:
            # Start all cameras
            for camera_id, camera in self.cameras.items():
                if not camera._is_running:
                    camera.start()
                
                # Create video writer
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_path = os.path.join(self.base_path, f"{camera_id}_{timestamp}.mp4")
                self.video_writers[camera_id] = cv2.VideoWriter(
                    video_path,
                    fourcc,
                    camera.config['fps'],
                    (camera.config['width'], camera.config['height'])
                )
                
                # Create CSV file for timestamps and metadata
                csv_path = os.path.join(self.base_path, f"{camera_id}_{timestamp}_metadata.csv")
                self.csv_files[camera_id] = open(csv_path, 'w', newline='')
                self.csv_writers[camera_id] = csv.DictWriter(
                    self.csv_files[camera_id],
                    fieldnames=['frame_number', 'timestamp', 'exposure', 'gain', 'fps']
                )
                self.csv_writers[camera_id].writeheader()
                
                # Start recording thread for this camera
                self.recording_threads[camera_id] = Thread(
                    target=self._camera_recording_thread,
                    args=(camera_id,),
                    daemon=True
                )
                self.recording_threads[camera_id].start()
            
            self.is_recording = True
            logger.info(f"Started recording to {self.base_path}")
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            self.stop()
            raise
            
    def stop(self):
        """Stop recording from all cameras."""
        if not self.is_recording:
            return
            
        self.stop_event.set()
        
        # Wait for all recording threads to finish
        for thread in self.recording_threads.values():
            thread.join()
            
        # Close all video writers and CSV files
        for writer in self.video_writers.values():
            writer.release()
        for csv_file in self.csv_files.values():
            csv_file.close()
            
        self.video_writers.clear()
        self.csv_files.clear()
        self.csv_writers.clear()
        self.is_recording = False
        self.stop_event.clear()
        
        logger.info("Stopped recording")
        
    def _camera_recording_thread(self, camera_id: str):
        """Thread function for recording from a single camera."""
        camera = self.cameras[camera_id]
        frame_queue = self.frame_queues[camera_id]
        queue_lock = self.queue_locks[camera_id]
        
        while not self.stop_event.is_set():
            try:
                # Get next frame from camera
                frame_data = next(camera)
                if frame_data is None:
                    continue
                    
                frame_number = self.frame_counts[camera_id]
                self.frame_counts[camera_id] += 1
                
                # Create frame object
                camera_frame = CameraFrame(
                    timestamp=frame_data['timestamp'],
                    frame_number=frame_number,
                    camera_id=camera_id,
                    image=frame_data['image'],
                    metadata={
                        'exposure': frame_data['exposure'],
                        'gain': frame_data['gain'],
                        'fps': frame_data['fps']
                    }
                )
                
                # Write frame to video file
                self.video_writers[camera_id].write(frame_data['image'])
                
                # Write metadata to CSV
                self.csv_writers[camera_id].writerow({
                    'frame_number': frame_number,
                    'timestamp': frame_data['timestamp'],
                    'exposure': frame_data['exposure'],
                    'gain': frame_data['gain'],
                    'fps': frame_data['fps']
                })
                
                # Add frame to queue for synchronization
                with queue_lock:
                    if frame_queue.full():
                        frame_queue.get()  # Remove oldest frame if queue is full
                    frame_queue.put(camera_frame)
                    
            except StopIteration:
                logger.warning(f"Camera {camera_id} stream ended")
                break
            except Exception as e:
                logger.error(f"Error recording from camera {camera_id}: {e}")
                continue
                
    def get_synchronized_frames(self, timestamp: float, max_time_diff: float = 0.1) -> Optional[Dict[str, CameraFrame]]:
        """Get synchronized frames from all cameras closest to the given timestamp.
        
        Args:
            timestamp: Target timestamp to synchronize with
            max_time_diff: Maximum allowed time difference in seconds
            
        Returns:
            Dictionary of camera_id -> CameraFrame pairs, or None if no synchronized frames found
        """
        synchronized_frames = {}
        
        for camera_id, frame_queue in self.frame_queues.items():
            with self.queue_locks[camera_id]:
                if frame_queue.empty():
                    return None
                    
                # Find frame closest to target timestamp
                best_frame = None
                min_time_diff = float('inf')
                
                # Make a copy of frames to search through
                frames = []
                while not frame_queue.empty():
                    frames.append(frame_queue.get())
                    
                for frame in frames:
                    time_diff = abs(frame.timestamp - timestamp)
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        best_frame = frame
                        
                # Put frames back in queue
                for frame in frames:
                    frame_queue.put(frame)
                    
                if best_frame is None or min_time_diff > max_time_diff:
                    return None
                    
                synchronized_frames[camera_id] = best_frame
                
        return synchronized_frames if len(synchronized_frames) == len(self.cameras) else None 