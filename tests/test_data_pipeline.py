import pytest
import numpy as np
import os
import datetime
import uuid
from pathlib import Path

# Assuming xwr68xxisk is in PYTHONPATH or tests are run from project root
from xwr68xxisk.data_management.recording_utils import save_recording, load_recording
from xwr68xxisk.data_management.recorder import DataRecorder
from xwr68xxisk.data_management.replayer import DataReplayer

@pytest.fixture
def temp_recordings_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test recordings."""
    recordings_dir = tmp_path / "recordings"
    recordings_dir.mkdir()
    return recordings_dir

@pytest.fixture
def sample_frames_and_metadata():
    """Provide sample frames and basic metadata for testing."""
    frames = [
        np.array([[1, 2], [3, 4]], dtype=np.int32),
        np.array([[5, 6], [7, 8]], dtype=np.int32),
        np.array([[9, 10], [11, 12]], dtype=np.int32),
    ]
    stacked_frames = np.stack(frames)
    metadata = {
        'test_id': str(uuid.uuid4()),
        'description': 'Sample data for pytest',
        'sensor_type': 'virtual_radar_v1'
    }
    return stacked_frames, metadata, frames # Return individual frames too for recorder test

# --- Tests for recording_utils.py ---

def test_save_and_load_recording_utility(temp_recordings_dir: Path, sample_frames_and_metadata):
    """Test saving and loading a recording using utility functions."""
    original_data, original_metadata, _ = sample_frames_and_metadata
    filepath = temp_recordings_dir / "utility_test.npz"

    save_recording(str(filepath), original_data, original_metadata)
    assert filepath.exists()

    loaded_data, loaded_metadata = load_recording(str(filepath))

    assert loaded_data is not None
    assert loaded_metadata is not None
    assert np.array_equal(loaded_data, original_data)
    # For dicts, direct comparison is usually fine for simple, flat dicts from JSON-like sources
    assert loaded_metadata == original_metadata

def test_load_non_existent_file_utility(temp_recordings_dir: Path):
    """Test loading a non-existent file using load_recording utility."""
    filepath = temp_recordings_dir / "non_existent.npz"
    loaded_data, loaded_metadata = load_recording(str(filepath))
    assert loaded_data is None
    assert loaded_metadata is None

# --- Tests for DataRecorder --- 

@pytest.fixture
def data_recorder(temp_recordings_dir: Path) -> DataRecorder:
    """Fixture to provide a DataRecorder instance."""
    initial_meta = {'recorder_type': 'test_recorder'}
    return DataRecorder(base_recordings_dir=str(temp_recordings_dir), initial_session_metadata=initial_meta)

def test_recorder_full_cycle(data_recorder: DataRecorder, sample_frames_and_metadata, temp_recordings_dir: Path):
    """Test DataRecorder: start, add frames, stop and save. Then verify."""
    stacked_frames, base_metadata, individual_frames = sample_frames_and_metadata
    sensor_config = {'mode': 'test_mode', 'rate': 10}
    session_description = "A test recording session"

    data_recorder.start_session(sensor_configuration=sensor_config, description=session_description)
    for frame in individual_frames:
        data_recorder.add_frame(frame)
    
    additional_save_meta = {'saved_by': 'pytest'}
    saved_filepath_str = data_recorder.stop_and_save_session(additional_metadata=additional_save_meta)
    
    assert saved_filepath_str is not None
    saved_filepath = Path(saved_filepath_str)
    assert saved_filepath.exists()
    assert saved_filepath.parent == temp_recordings_dir

    # Verify recorder state reset
    assert not data_recorder.is_recording
    assert data_recorder.current_session_id is None
    assert not data_recorder.frames_buffer

    # Verify saved content
    loaded_data, loaded_metadata = load_recording(saved_filepath_str)
    assert loaded_data is not None
    assert loaded_metadata is not None
    assert np.array_equal(loaded_data, stacked_frames)
    
    assert loaded_metadata['recorder_type'] == 'test_recorder' # Initial meta
    assert loaded_metadata['sensor_configuration'] == sensor_config
    assert loaded_metadata['description'] == session_description
    assert loaded_metadata['saved_by'] == 'pytest' # Additional meta
    assert loaded_metadata['frame_count'] == len(individual_frames)
    assert 'session_id' in loaded_metadata
    assert 'session_timestamp_utc' in loaded_metadata
    assert 'session_duration_seconds' in loaded_metadata

def test_recorder_empty_session(data_recorder: DataRecorder):
    """Test DataRecorder correctly handles a session with no frames."""
    sensor_config = {'mode': 'empty_test'}
    data_recorder.start_session(sensor_configuration=sensor_config, description="Empty session")
    saved_filepath = data_recorder.stop_and_save_session()
    
    assert saved_filepath is None
    assert not data_recorder.is_recording # State should still reset

def test_recorder_add_frame_no_session(data_recorder: DataRecorder, capsys):
    """Test DataRecorder warns and does not add frame if no session is active."""
    # Ensure recorder is in a state where no session is active (default or after stop)
    assert not data_recorder.is_recording
    frame = np.array([1, 2, 3])
    data_recorder.add_frame(frame)
    
    assert not data_recorder.frames_buffer # Buffer should be empty
    captured = capsys.readouterr()
    assert "Warning: No active recording session. Frame not added." in captured.out

# --- Tests for DataReplayer --- 

@pytest.fixture
def sample_recorded_file(data_recorder: DataRecorder, sample_frames_and_metadata, temp_recordings_dir: Path) -> str:
    """Creates a sample recording and returns its file path."""
    _, _, individual_frames = sample_frames_and_metadata # Use individual frames for recorder
    sensor_config = {'mode': 'replay_test'}
    data_recorder.start_session(sensor_configuration=sensor_config, description="For replayer test")
    for frame in individual_frames:
        data_recorder.add_frame(frame)
    filepath = data_recorder.stop_and_save_session()
    assert filepath is not None
    return filepath

def test_replayer_load_and_play(sample_recorded_file: str, sample_frames_and_metadata):
    """Test DataReplayer: load, get metadata, iterate frames."""
    stacked_frames, original_metadata_sample, _ = sample_frames_and_metadata
    # Note: original_metadata_sample is the base, recorder adds more.

    replayer = DataReplayer(filepath=sample_recorded_file)
    assert replayer.is_loaded
    assert replayer.filepath == sample_recorded_file
    assert replayer.total_frames == len(stacked_frames)

    loaded_meta = replayer.metadata
    assert loaded_meta is not None
    assert loaded_meta['description'] == "For replayer test"
    assert loaded_meta['sensor_configuration'] == {'mode': 'replay_test'}
    assert loaded_meta['frame_count'] == len(stacked_frames)

    replayed_frames_list = []
    frame_num_counter = 1
    while replayer.has_more_frames():
        assert replayer.current_frame_number == frame_num_counter
        frame = replayer.get_next_frame()
        assert frame is not None
        replayed_frames_list.append(frame)
        frame_num_counter += 1
    
    assert not replayer.has_more_frames()
    assert replayer.get_next_frame() is None # Should be None after all frames are out
    assert len(replayed_frames_list) == len(stacked_frames)
    
    replayed_data_stacked = np.stack(replayed_frames_list)
    assert np.array_equal(replayed_data_stacked, stacked_frames)

def test_replayer_rewind(sample_recorded_file: str, sample_frames_and_metadata):
    """Test DataReplayer rewind functionality."""
    stacked_frames, _, _ = sample_frames_and_metadata
    replayer = DataReplayer(filepath=sample_recorded_file)
    assert replayer.is_loaded

    # Play through a few frames
    _ = replayer.get_next_frame()
    _ = replayer.get_next_frame()
    assert replayer.current_frame_number == 3 # Next frame would be 3rd

    replayer.rewind()
    assert replayer.current_frame_number == 1
    assert replayer.has_more_frames()

    first_frame_after_rewind = replayer.get_next_frame()
    assert first_frame_after_rewind is not None
    assert np.array_equal(first_frame_after_rewind, stacked_frames[0])

def test_replayer_load_non_existent_file():
    """Test DataReplayer loading a non-existent file."""
    replayer = DataReplayer()
    success = replayer.load_session("path/to/non_existent_file.npz")
    assert not success
    assert not replayer.is_loaded
    assert replayer.metadata is None
    assert replayer.total_frames == 0
    assert replayer.get_next_frame() is None


# To make xwr68xxisk.data_management importable, ensure:
# 1. tests/ is at the same level as xwr68xxisk/ OR the project root is in PYTHONPATH.
# 2. xwr68xxisk/ has an __init__.py
# 3. xwr68xxisk/data_management/ has an __init__.py
# Example command to run tests from project root:
# python -m pytest 