import pytest
import numpy as np
from opencv_camera import OpenCVCamera  # Assuming this is the correct import

@pytest.fixture
def camera():
    """Fixture to create and cleanup camera instance."""
    camera = OpenCVCamera(device_id=0)
    yield camera
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
    assert camera._cap is not None
    camera.stop()
    assert not camera._is_running
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

    
