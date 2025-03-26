"""Tests for the CameraRecorder class."""

import os
import time
import pytest
import numpy as np
from pathlib import Path
from xwr68xxisk.cameras import OpenCVCamera
from xwr68xxisk.camera_recorder import CameraRecorder
from test_cameras import MockCamera  # Import the MockCamera class
import cv2

@pytest.fixture
def temp_recording_dir(tmp_path):
    """Create a temporary directory for recordings."""
    recording_dir = tmp_path / "recordings"
    recording_dir.mkdir()
    return str(recording_dir)

@pytest.fixture
def mock_cameras():
    """Create two mock cameras for testing."""
    try:
        # Try to create real cameras first
        cameras = {
            'cam1': OpenCVCamera(device_id=0),
            'cam2': OpenCVCamera(device_id=1)
        }
        # Test if we can actually use them
        for camera in cameras.values():
            try:
                camera.start()
                camera.stop()
            except (RuntimeError, cv2.error):
                # If any camera fails, fall back to mock cameras
                cameras = {
                    'cam1': MockCamera(device_id=0),
                    'cam2': MockCamera(device_id=1)
                }
                break
    except (RuntimeError, cv2.error):
        # Fall back to mock cameras if real cameras are not available
        cameras = {
            'cam1': MockCamera(device_id=0),
            'cam2': MockCamera(device_id=1)
        }
    return cameras

@pytest.fixture
def recorder(temp_recording_dir, mock_cameras):
    """Create a camera recorder instance."""
    recorder = CameraRecorder(temp_recording_dir, mock_cameras)
    yield recorder
    recorder.stop()

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
    assert all(camera._is_running for camera in recorder.cameras.values())
    
    # Record a few frames
    time.sleep(0.5)
    
    recorder.stop()
    assert not recorder.is_recording
    assert all(not camera._is_running for camera in recorder.cameras.values())
    
    # Check that files were created
    recording_dir = Path(temp_recording_dir)
    video_files = list(recording_dir.glob("*.mp4"))
    metadata_files = list(recording_dir.glob("*_metadata.csv"))
    
    assert len(video_files) == len(recorder.cameras)
    assert len(metadata_files) == len(recorder.cameras)

def test_synchronized_frames(recorder):
    """Test getting synchronized frames."""
    recorder.start()
    
    # Record a few frames
    time.sleep(0.5)
    
    # Check that frames are being recorded
    for camera_id, queue in recorder.frame_queues.items():
        assert not queue.empty()
    
    recorder.stop()

def test_recorder_cleanup(recorder):
    """Test that resources are properly cleaned up."""
    recorder.start()
    time.sleep(0.1)
    recorder.stop()
    
    # Check that all resources are cleaned up
    assert all(writer is None for writer in recorder.video_writers.values())
    assert all(file.closed for file in recorder.csv_files.values())
    assert not any(thread.is_alive() for thread in recorder.recording_threads.values()) 