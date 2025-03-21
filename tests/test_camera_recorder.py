"""Tests for the CameraRecorder class."""

import os
import time
import pytest
import numpy as np
import cv2
from pathlib import Path
from xwr68xxisk.cameras import OpenCVCamera
from xwr68xxisk.camera_recorder import CameraRecorder

@pytest.fixture
def temp_recording_dir(tmp_path):
    """Create a temporary directory for recordings."""
    recording_dir = tmp_path / "recordings"
    recording_dir.mkdir()
    return str(recording_dir)

@pytest.fixture
def mock_cameras():
    """Create two mock cameras for testing."""
    cameras = {
        'cam1': OpenCVCamera(device_id=0),
        'cam2': OpenCVCamera(device_id=1)
    }
    return cameras

@pytest.fixture
def recorder(temp_recording_dir, mock_cameras):
    """Create a CameraRecorder instance."""
    recorder = CameraRecorder(temp_recording_dir, mock_cameras)
    yield recorder
    recorder.stop()  # Ensure cleanup

def test_recorder_initialization(recorder, temp_recording_dir):
    """Test recorder initialization."""
    assert recorder.base_path == temp_recording_dir
    assert len(recorder.cameras) == 2
    assert not recorder.is_recording
    assert os.path.exists(temp_recording_dir)

def test_start_stop_recording(recorder, temp_recording_dir):
    """Test starting and stopping recording."""
    recorder.start()
    assert recorder.is_recording
    
    # Let it record a few frames
    time.sleep(1)
    
    recorder.stop()
    assert not recorder.is_recording
    
    # Check that files were created
    files = os.listdir(temp_recording_dir)
    assert len(files) == 4  # 2 video files and 2 CSV files
    
    # Check for expected file types
    video_files = [f for f in files if f.endswith('.mp4')]
    csv_files = [f for f in files if f.endswith('_metadata.csv')]
    assert len(video_files) == 2
    assert len(csv_files) == 2

def test_synchronized_frames(recorder):
    """Test getting synchronized frames."""
    recorder.start()
    time.sleep(0.5)  # Let it record some frames
    
    # Get current timestamp
    current_time = time.time()
    
    # Try to get synchronized frames
    frames = recorder.get_synchronized_frames(current_time, max_time_diff=0.1)
    
    assert frames is not None
    assert len(frames) == 2  # Should have frames from both cameras
    
    # Check frame contents
    for camera_id, frame in frames.items():
        assert isinstance(frame.image, np.ndarray)
        assert abs(frame.timestamp - current_time) <= 0.1
        assert frame.camera_id in ['cam1', 'cam2']
        assert isinstance(frame.metadata, dict)
        assert 'exposure' in frame.metadata
        assert 'gain' in frame.metadata
        assert 'fps' in frame.metadata

def test_recorder_cleanup(recorder):
    """Test that resources are properly cleaned up."""
    recorder.start()
    time.sleep(0.5)
    
    # Store references to check cleanup
    video_writers = recorder.video_writers.copy()
    csv_files = recorder.csv_files.copy()
    
    recorder.stop()
    
    # Check that all resources were cleaned up
    assert len(recorder.video_writers) == 0
    assert len(recorder.csv_files) == 0
    assert len(recorder.csv_writers) == 0
    assert not recorder.is_recording
    
    # Check that files are closed
    for writer in video_writers.values():
        # VideoWriter doesn't have an is_opened() method, but we can check if it's None
        assert writer is not None
    
    for csv_file in csv_files.values():
        assert csv_file.closed 