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
        import cv2
        self.cv2 = cv2  # Store cv2 as instance variable
        
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
        self._cap = self.cv2.VideoCapture(self._device_id)
        if not self._cap.isOpened():
            raise RuntimeError(f"Failed to open camera with device ID {self._device_id}")
            
        # Set camera properties based on config
        self._cap.set(self.cv2.CAP_PROP_FRAME_WIDTH, self._config['width'])
        self._cap.set(self.cv2.CAP_PROP_FRAME_HEIGHT, self._config['height'])
        self._cap.set(self.cv2.CAP_PROP_FPS, self._config['fps'])
        
        # Set minimal buffer size to reduce latency
        self._cap.set(self.cv2.CAP_PROP_BUFFERSIZE, self._config['buffer_size'])
        
        # Set backend-specific optimizations if available
        backend = self._cap.getBackendName()
        if backend == 'V4L2':
            # Linux-specific optimizations
            self._cap.set(self.cv2.CAP_PROP_FOURCC, self.cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
        
        if self._config['exposure'] > 0:
            self._cap.set(self.cv2.CAP_PROP_AUTO_EXPOSURE, 0)  # Disable auto exposure
            self._cap.set(self.cv2.CAP_PROP_EXPOSURE, self._config['exposure'])
            
        if self._config['gain'] > 0:
            self._cap.set(self.cv2.CAP_PROP_GAIN, self._config['gain'])

        # Set focus control
        if not self._config['autofocus']:
            self._cap.set(self.cv2.CAP_PROP_AUTOFOCUS, 0)  # Disable autofocus
            if self._config['focus'] > 0:
                self._cap.set(self.cv2.CAP_PROP_FOCUS, self._config['focus'])
        else:
            self._cap.set(self.cv2.CAP_PROP_AUTOFOCUS, 1)  # Enable autofocus
            
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
        current_fps = self._cap.get(self.cv2.CAP_PROP_FPS)
        current_exposure = self._cap.get(self.cv2.CAP_PROP_EXPOSURE)
        current_gain = self._cap.get(self.cv2.CAP_PROP_GAIN)
        
        return {
            'image': frame,
            'timestamp': self._last_frame_time,
            'exposure': current_exposure,
            'gain': current_gain,
            'fps': current_fps,
            'width': frame.shape[1],
            'height': frame.shape[0],
            'focus': self._cap.get(self.cv2.CAP_PROP_FOCUS),
            'autofocus': bool(self._cap.get(self.cv2.CAP_PROP_AUTOFOCUS))
        }

class RealSenseCamera(BaseCamera):
    """Intel RealSense camera implementation."""
    
    def __init__(self, device_id: Optional[str] = None):
        """Initialize the RealSense camera.
        
        Args:
            device_id: The serial number of the camera (default: None, uses first available)
        """
        super().__init__()
        import pyrealsense2 as rs
        self._rs = rs  # Store the module for later use
        self._device_id = device_id
        self._pipeline = None
        self._config = {
            'fps': 30,
            'width': 640,
            'height': 480,
            'depth_enabled': True,
            'color_format': rs.format.bgr8,
            'depth_format': rs.format.z16,
            'stream_index': 0,
            'exposure': -1,  # Auto exposure
            'gain': -1,      # Auto gain
            'emitter_enabled': True,  # IR emitter for depth
            'laser_power': 360,       # Laser power (0-360)
        }
        self._align = None
        
    def start(self):
        """Start the RealSense camera."""
        import pyrealsense2 as rs
        
        self._pipeline = self._rs.pipeline()
        rs_config = self._rs.config()
        
        # If a specific device is requested, try to enable it
        if self._device_id:
            rs_config.enable_device(self._device_id)
        
        # Configure color stream
        rs_config.enable_stream(
            self._rs.stream.color,
            self._config['width'],
            self._config['height'],
            self._config['color_format'],
            self._config['fps']
        )
        
        # Configure depth stream if enabled
        if self._config['depth_enabled']:
            rs_config.enable_stream(
                self._rs.stream.depth,
                self._config['width'],
                self._config['height'],
                self._config['depth_format'],
                self._config['fps']
            )
            # Create alignment object to align depth frames to color frames
            self._align = self._rs.align(self._rs.stream.color)
        
        # Start streaming
        profile = self._pipeline.start(rs_config)
        
        # Configure additional camera settings
        selected_device = profile.get_device()
        depth_sensor = selected_device.first_depth_sensor()
        
        # Configure depth sensor options if available
        if depth_sensor:
            # Enable/disable the IR emitter
            if depth_sensor.supports(self._rs.option.emitter_enabled):
                depth_sensor.set_option(
                    self._rs.option.emitter_enabled, 
                    1 if self._config['emitter_enabled'] else 0
                )
            
            # Set laser power if supported
            if depth_sensor.supports(self._rs.option.laser_power):
                depth_sensor.set_option(
                    self._rs.option.laser_power,
                    self._config['laser_power']
                )
        
        # Configure color sensor options
        color_sensor = selected_device.first_color_sensor()
        if color_sensor:
            # Set manual exposure if specified
            if self._config['exposure'] > 0 and color_sensor.supports(self._rs.option.exposure):
                color_sensor.set_option(self._rs.option.enable_auto_exposure, 0)
                color_sensor.set_option(self._rs.option.exposure, self._config['exposure'])
            
            # Set manual gain if specified
            if self._config['gain'] > 0 and color_sensor.supports(self._rs.option.gain):
                color_sensor.set_option(self._rs.option.enable_auto_exposure, 0)
                color_sensor.set_option(self._rs.option.gain, self._config['gain'])
        
        # Wait for camera to stabilize
        for _ in range(5):
            self._pipeline.wait_for_frames()
            
        super().start()
    
    def stop(self):
        """Stop the RealSense camera."""
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            finally:
                self._pipeline = None
        super().stop()
    
    def __next__(self) -> Dict[str, Any]:
        """Get the next frame from the camera.
        
        Returns:
            Dict containing the image, depth (if enabled), and metadata
        """
        if not self._is_running or self._pipeline is None:
            raise StopIteration
        
        timestamp = time.time()
        
        # Wait for a coherent set of frames
        frames = self._pipeline.wait_for_frames()
        
        # Align depth to color frame if depth is enabled and alignment is configured
        if self._config['depth_enabled'] and self._align:
            frames = self._align.process(frames)
        
        # Get color frame
        color_frame = frames.get_color_frame()
        if not color_frame:
            return self.__next__()  # Try again if no color frame
        
        # Convert color frame to numpy array
        color_image = np.asanyarray(color_frame.get_data())
        
        result = {
            'image': color_image,
            'timestamp': timestamp,
            'width': color_image.shape[1],
            'height': color_image.shape[0],
            'fps': self._config['fps'],
        }
        
        # Get depth frame if enabled
        if self._config['depth_enabled']:
            depth_frame = frames.get_depth_frame()
            if depth_frame:
                depth_image = np.asanyarray(depth_frame.get_data())
                result['depth'] = depth_image
        
        # Get camera settings/metadata
        try:
            profile = color_frame.get_profile()
            device = profile.get_device()
            color_sensor = device.first_color_sensor()
            
            if color_sensor:
                if color_sensor.supports(self._rs.option.exposure):
                    result['exposure'] = color_sensor.get_option(self._rs.option.exposure)
                if color_sensor.supports(self._rs.option.gain):
                    result['gain'] = color_sensor.get_option(self._rs.option.gain)
        except Exception:
            # If we can't get metadata, continue without it
            pass
            
        return result

class DepthAICamera(BaseCamera):
    """Luxonis DepthAI camera implementation."""
    
    def __init__(self, device_id: Optional[str] = None):
        """Initialize the DepthAI camera.
        
        Args:
            device_id: The device ID/MX ID of the camera (default: None, uses first available)
        """
        super().__init__()
        import depthai as dai
        self._dai = dai  # Store the module for later use
        self._device_id = device_id
        self._device = None
        self._pipeline = None
        self._queues = {}
        self._config = {
            'fps': 30,
            'color_width': 1080,
            'color_height': 1080,
            'mono_width': 400,
            'mono_height': 400,
            'color_iso': 800,  # ISO value for color camera
            'color_exposure': 20000,  # Exposure time in microseconds, -1 for auto
            'isp_scale': (1, 3),  # Scale color frames to reduce size (1/3)
            'sync_nn': True,  # Sync all streams
            'lrcheck': True,  # Enable left-right check for better depth
            'extended_disparity': False,  # Extended disparity
            'subpixel': True,  # Subpixel mode
            'confidence_threshold': 200  # Depth confidence threshold
        }
        self._last_frame_time = 0
        self._frame_interval = 1.0 / self._config['fps']
        
    def start(self):
        """Start the DepthAI camera."""
        import depthai as dai
        
        # Create pipeline
        self._pipeline = self._dai.Pipeline()
        
        # Define sources and outputs
        camRgb = self._pipeline.create(self._dai.node.ColorCamera)
        left = self._pipeline.create(self._dai.node.MonoCamera)
        right = self._pipeline.create(self._dai.node.MonoCamera)
        
        rgbOut = self._pipeline.create(self._dai.node.XLinkOut)
        leftOut = self._pipeline.create(self._dai.node.XLinkOut)
        rightOut = self._pipeline.create(self._dai.node.XLinkOut)
        
        rgbOut.setStreamName("rgb")
        leftOut.setStreamName("left")
        rightOut.setStreamName("right")
        
        # Properties for RGB Camera
        camRgb.setBoardSocket(self._dai.CameraBoardSocket.RGB)
        camRgb.setResolution(self._dai.ColorCameraProperties.SensorResolution.THE_1080_P)
        camRgb.setFps(self._config['fps'])
        
        if self._config['color_exposure'] > 0:
            camRgb.initialControl.setManualExposure(
                self._config['color_exposure'],
                self._config['color_iso']
            )
        
        # Set ISP scale to reduce the frame size
        scale_num, scale_denom = self._config['isp_scale']
        camRgb.setIspScale(scale_num, scale_denom)
        
        # Properties for Mono Cameras (Left and Right)
        left.setResolution(self._dai.MonoCameraProperties.SensorResolution.THE_400_P)
        left.setBoardSocket(self._dai.CameraBoardSocket.LEFT)
        left.setFps(self._config['fps'])
        
        right.setResolution(self._dai.MonoCameraProperties.SensorResolution.THE_400_P)
        right.setBoardSocket(self._dai.CameraBoardSocket.RIGHT)
        right.setFps(self._config['fps'])
        
        # Linking
        camRgb.isp.link(rgbOut.input)
        left.out.link(leftOut.input)
        right.out.link(rightOut.input)
        
        # If depth processing is needed, we can add a stereo depth node
        if self._config.get('depth_enabled', True):
            stereo = self._pipeline.create(self._dai.node.StereoDepth)
            depthOut = self._pipeline.create(self._dai.node.XLinkOut)
            depthOut.setStreamName("depth")
            
            # Configure stereo depth
            stereo.setDefaultProfilePreset(self._dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
            stereo.setLeftRightCheck(self._config['lrcheck'])
            stereo.setExtendedDisparity(self._config['extended_disparity'])
            stereo.setSubpixel(self._config['subpixel'])
            
            # Set confidence threshold
            confidence_threshold = self._config['confidence_threshold']
            stereo.initialConfig.setConfidenceThreshold(confidence_threshold)
            
            # Link cameras with stereo node
            left.out.link(stereo.left)
            right.out.link(stereo.right)
            
            # Link stereo output to XLink
            stereo.depth.link(depthOut.input)
        
        # Connect to device and start pipeline
        if self._device_id:
            found = False
            for device_info in self._dai.Device.getAllAvailableDevices():
                if device_info.getMxId() == self._device_id:
                    self._device = self._dai.Device(self._pipeline, device_info)
                    found = True
                    break
            if not found:
                raise RuntimeError(f"Device with ID {self._device_id} not found")
        else:
            self._device = self._dai.Device(self._pipeline)
            
        # Get output queues
        self._queues = {
            "rgb": self._device.getOutputQueue(name="rgb", maxSize=4, blocking=False),
            "left": self._device.getOutputQueue(name="left", maxSize=4, blocking=False),
            "right": self._device.getOutputQueue(name="right", maxSize=4, blocking=False)
        }
        
        if self._config.get('depth_enabled', True):
            self._queues["depth"] = self._device.getOutputQueue(name="depth", maxSize=4, blocking=False)
        
        self._last_frame_time = time.time()
        super().start()
        
    def stop(self):
        """Stop the DepthAI camera."""
        if self._device is not None:
            try:
                self._device.close()
            finally:
                self._device = None
                self._pipeline = None
                self._queues = {}
        super().stop()
        
    def __next__(self) -> Dict[str, Any]:
        """Get the next frame from the camera.
        
        Returns:
            Dict containing the images (rgb, left, right, depth) and metadata
        """
        if not self._is_running or self._device is None:
            raise StopIteration
            
        current_time = time.time()
        elapsed = current_time - self._last_frame_time
        
        # Maintain frame rate
        if elapsed < self._frame_interval:
            time.sleep(self._frame_interval - elapsed)
        
        # Get frames from all cameras
        frame_data = {}
        
        # Get RGB frame
        rgb_frame = self._queues["rgb"].get()
        if rgb_frame is not None:
            frame_data["image"] = rgb_frame.getCvFrame()  # Standard API expects "image" key

        # Get left mono frame
        left_frame = self._queues["left"].get()
        if left_frame is not None:
            frame_data["left"] = left_frame.getCvFrame()

        # Get right mono frame
        right_frame = self._queues["right"].get()
        if right_frame is not None:
            frame_data["right"] = right_frame.getCvFrame()
            
        # Get depth frame if enabled
        if "depth" in self._queues:
            depth_frame = self._queues["depth"].get()
            if depth_frame is not None:
                frame_data["depth"] = depth_frame.getCvFrame()
        
        self._last_frame_time = time.time()
        
        # Add metadata
        frame_data.update({
            'timestamp': self._last_frame_time,
            'fps': self._config['fps'],
            'width': frame_data.get('image', frame_data.get('left')).shape[1] if 'image' in frame_data or 'left' in frame_data else None,
            'height': frame_data.get('image', frame_data.get('left')).shape[0] if 'image' in frame_data or 'left' in frame_data else None,
            'exposure': self._config['color_exposure'],
            'iso': self._config['color_iso']
        })
        
        return frame_data

class RaspberryPiCamera(BaseCamera):
    """Raspberry Pi Camera implementation using libcamera2."""
    
    def __init__(self):
        """Initialize the Raspberry Pi camera."""
        super().__init__()
        import picamera2
        self._picam2 = None
        self._config = {
            'fps': 30,
            'width': 1920,
            'height': 1080,
            'exposure': -1,  # Auto exposure
            'gain': -1,      # Auto gain
            'buffer_size': 1,  # Minimize buffer size
            'autofocus': True,  # Enable autofocus by default
            'focus': -1,      # Focus value when autofocus is disabled
        }
        self._last_frame_time = 0
        self._frame_interval = 1.0 / self._config['fps']
        
    def start(self):
        """Start the Raspberry Pi camera."""
        from picamera2 import Picamera2
        
        self._picam2 = Picamera2()
        
        # Configure camera for video streaming
        config = self._picam2.create_video_configuration(
            main={"size": (self._config['width'], self._config['height'])},
            controls={
                "FrameDurationLimits": (int(1e6 / self._config['fps']), int(1e6 / self._config['fps']))
            }
        )
        
        self._picam2.configure(config)
        
        # Set manual exposure and gain if specified
        if self._config['exposure'] > 0:
            self._picam2.set_controls({"ExposureTime": self._config['exposure']})
        if self._config['gain'] > 0:
            self._picam2.set_controls({"AnalogueGain": self._config['gain']})
            
        # Start the camera
        self._picam2.start()
        
        # Wait for camera to stabilize
        time.sleep(2)
        
        self._last_frame_time = time.time()
        super().start()
        
    def stop(self):
        """Stop the Raspberry Pi camera."""
        if self._picam2 is not None:
            try:
                self._picam2.stop()
                self._picam2.close()
            finally:
                self._picam2 = None
        super().stop()
        
    def __next__(self) -> Dict[str, Any]:
        """Get the next frame from the camera.
        
        Returns:
            Dict containing the image and metadata
        """
        if not self._is_running or self._picam2 is None:
            raise StopIteration
            
        current_time = time.time()
        elapsed = current_time - self._last_frame_time
        
        # Maintain frame rate
        if elapsed < self._frame_interval:
            time.sleep(self._frame_interval - elapsed)
            
        # Capture frame
        frame = self._picam2.capture_array()
        
        self._last_frame_time = time.time()
        
        # Get current camera metadata
        metadata = self._picam2.capture_metadata()
        
        return {
            'image': frame,
            'timestamp': self._last_frame_time,
            'exposure': metadata.get('ExposureTime', -1),
            'gain': metadata.get('AnalogueGain', -1),
            'fps': self._config['fps'],
            'width': frame.shape[1],
            'height': frame.shape[0]
        }

    

