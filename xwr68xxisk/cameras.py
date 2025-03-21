"""Interface for cameras

Interface for cameras to capture images synchronized with the Radar

- Webcam
- Raspberry Pi Camera
- Realsense
- Depthai Lunxonis

Create a base class for all cameras that provides a common interface for capturing images including metadata.
The images are returned as a dictionary with the following keys:
- image: The image as a numpy array
- timestamp: The timestamp of the image
- exposure: The exposure time of the image
- gain: The gain of the image
- fps: The frame rate of the image
- width: The width of the image
- height: The height of the image

The base class should define the following methods:
- start()
- stop()
- __iter__()
- __next__()
- configuration setter and getter

Example usage:
    ```python
    camera = OpenCVCamera(device_id=0)  # Use default webcam
    camera.start()

    try:
        for frame_data in camera:
            image = frame_data['image']
            # Process frame as needed
            cv2.imshow('Camera', image)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
    ```
"""

import cv2
import numpy as np
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseCamera(ABC):
    """Base class for all cameras."""
    
    def __init__(self):
        self._is_running = False
        self._config = {}
        
    @property
    def config(self) -> Dict[str, Any]:
        """Get the current camera configuration."""
        return self._config
        
    @config.setter
    def config(self, value: Dict[str, Any]):
        """Set the camera configuration."""
        self._config = value
        
    @abstractmethod
    def start(self):
        """Start the camera."""
        self._is_running = True
        
    @abstractmethod
    def stop(self):
        """Stop the camera."""
        self._is_running = False
        
    def __iter__(self):
        """Make the camera iterable."""
        return self
        
    @abstractmethod
    def __next__(self) -> Dict[str, Any]:
        """Get the next frame from the camera.
        
        Returns:
            Dict containing the image and metadata
        """
        if not self._is_running:
            raise StopIteration
            

class OpenCVCamera(BaseCamera):
    """OpenCV camera implementation."""
    
    def __init__(self, device_id: int = 0):
        """Initialize the OpenCV camera.
        
        Args:
            device_id: The device ID of the camera (default: 0)
        """
        super().__init__()
        self._device_id = device_id
        self._cap = None
        self._config = {
            'fps': 30,  # More stable FPS
            'width': 640,
            'height': 480,
            'exposure': -1,  # Auto exposure
            'gain': -1,      # Auto gain
            'buffer_size': 1,  # Minimize buffer size
            'autofocus': True,  # Enable autofocus by default
            'focus': -1,      # Focus value when autofocus is disabled
        }
        self._last_frame_time = 0
        self._frame_interval = 1.0 / self._config['fps']
        
    def start(self):
        """Start the camera capture."""
        self._cap = cv2.VideoCapture(self._device_id)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera with device ID {self._device_id}")
            
        # Set camera properties based on config
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._config['width'])
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._config['height'])
        self._cap.set(cv2.CAP_PROP_FPS, self._config['fps'])
        
        # Set minimal buffer size to reduce latency
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, self._config['buffer_size'])
        
        # Set backend-specific optimizations if available
        backend = self._cap.getBackendName()
        if backend == 'V4L2':
            # Linux-specific optimizations
            self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        
        if self._config['exposure'] > 0:
            self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0)  # Disable auto exposure
            self._cap.set(cv2.CAP_PROP_EXPOSURE, self._config['exposure'])
            
        if self._config['gain'] > 0:
            self._cap.set(cv2.CAP_PROP_GAIN, self._config['gain'])

        # Set focus control
        if not self._config['autofocus']:
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)  # Disable autofocus
            if self._config['focus'] > 0:
                self._cap.set(cv2.CAP_PROP_FOCUS, self._config['focus'])
        else:
            self._cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable autofocus
            
        # Clear the buffer
        for _ in range(5):
            self._cap.grab()
            
        self._last_frame_time = time.time()
        super().start()
        
    def stop(self):
        """Stop the camera capture."""
        if self._cap is not None:
            try:
                self._cap.release()
            finally:
                self._cap = None
        super().stop()
        
    def __next__(self) -> Dict[str, Any]:
        """Get the next frame from the camera.
        
        Returns:
            Dict containing the image and metadata
        """
        if not self._is_running or self._cap is None:
            raise StopIteration
            
        current_time = time.time()
        elapsed = current_time - self._last_frame_time
        
        # Skip frames if we're behind
        if elapsed < self._frame_interval:
            time.sleep(self._frame_interval - elapsed)
            
        # Use grab() and retrieve() instead of read() to minimize latency
        if not self._cap.grab():
            raise StopIteration
            
        ret, frame = self._cap.retrieve()
        if not ret:
            raise StopIteration
            
        self._last_frame_time = time.time()
        
        # Get current camera properties
        current_fps = self._cap.get(cv2.CAP_PROP_FPS)
        current_exposure = self._cap.get(cv2.CAP_PROP_EXPOSURE)
        current_gain = self._cap.get(cv2.CAP_PROP_GAIN)
        
        return {
            'image': frame,
            'timestamp': self._last_frame_time,
            'exposure': current_exposure,
            'gain': current_gain,
            'fps': current_fps,
            'width': frame.shape[1],
            'height': frame.shape[0],
            'focus': self._cap.get(cv2.CAP_PROP_FOCUS),
            'autofocus': bool(self._cap.get(cv2.CAP_PROP_AUTOFOCUS))
        }

    

