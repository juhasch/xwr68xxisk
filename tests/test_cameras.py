import pytest
import numpy as np
import cv2
import time
from xwr68xxisk.cameras import OpenCVCamera, BaseCamera


class MockCamera(BaseCamera):
    """Mock camera for testing."""
    
    def __init__(self, device_id: int = 0):
        super().__init__()
        self._device_id = device_id
        self._config = {
            'fps': 30,
            'width': 640,
            'height': 480,
            'exposure': -1,
            'gain': -1,
            'buffer_size': 1,
            'autofocus': True,
            'focus': -1,
        }
        self._frame_count = 0
        
    def start(self):
        """Start the mock camera."""
        self._is_running = True
        
    def stop(self):
        """Stop the mock camera."""
        self._is_running = False
        
    def __next__(self):
        """Generate a mock frame."""
        if not self._is_running:
            raise StopIteration
            
        # Create a simple test pattern
        frame = np.zeros((self._config['height'], self._config['width'], 3), dtype=np.uint8)
        # Add frame number as text
        cv2.putText(frame, f"Frame {self._frame_count}", (50, 50), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        self._frame_count += 1
        
        return {
            'image': frame,
            'timestamp': time.time(),
            'exposure': self._config['exposure'],
            'gain': self._config['gain'],
            'fps': self._config['fps'],
            'width': frame.shape[1],
            'height': frame.shape[0],
            'focus': self._config['focus'],
            'autofocus': self._config['autofocus']
        }


@pytest.fixture
def camera():
    """Fixture to create and cleanup camera instance."""
    try:
        # Try to create a real camera first
        camera = OpenCVCamera(device_id=0)
        camera.start()
        camera.stop()  # Test if we can actually start/stop it
        yield camera
    except (RuntimeError, cv2.error):
        # Fall back to mock camera if real camera is not available
        camera = MockCamera(device_id=0)
        yield camera
    finally:
        if camera._is_running:
            camera.stop()

def test_camera_configuration(camera):
    """Test camera configuration."""
    test_config = {
        'fps': 60,
        'width': 1280,
        'height': 720,
        'exposure': -1,
        'gain': -1,
    }
    camera.config = test_config
    assert camera.config == test_config

def test_camera_start_stop(camera):
    """Test camera start and stop."""
    assert not camera._is_running
    camera.start()
    assert camera._is_running
    if isinstance(camera, OpenCVCamera):
        assert camera._cap is not None
    camera.stop()
    assert not camera._is_running
    if isinstance(camera, OpenCVCamera):
        assert camera._cap is None

def test_frame_metadata(camera):
    """Test frame metadata."""
    camera.start()
    frame_data = next(camera)
    
    # Check if all required metadata is present
    required_keys = ['image', 'timestamp', 'exposure', 'gain', 'fps', 'width', 'height']
    for key in required_keys:
        assert key in frame_data
        
    # Check image dimensions
    assert frame_data['width'] == camera.config['width']
    assert frame_data['height'] == camera.config['height']
    
    # Check image type and shape
    assert isinstance(frame_data['image'], np.ndarray)
    assert frame_data['image'].shape[0] == camera.config['height']
    assert frame_data['image'].shape[1] == camera.config['width']

def test_iteration(camera):
    """Test camera iteration."""
    camera.start()
    frame_count = 0
    max_frames = 10
    
    for frame_data in camera:
        frame_count += 1
        if frame_count >= max_frames:
            break
            
    assert frame_count == max_frames

    
