import numpy as np
from typing import Optional, Dict, Any, Tuple
import os

# Assuming recording_utils.py and recorder.py are in the same directory or accessible in PYTHONPATH
from .recording_utils import load_recording #, save_recording # save_recording for example
from .recorder import DataRecorder # For example usage

class DataReplayer:
    """
    Loads a recorded data session from an .npz file and allows replaying it frame by frame.
    """
    def __init__(self, filepath: Optional[str] = None):
        """
        Initializes the DataReplayer.

        Parameters
        ----------
        filepath : Optional[str], optional
            The path to the .npz recording file to load immediately. 
            If None, no session is loaded initially. Use load_session() later.
            Defaults to None.
        """
        self._data_frames: Optional[np.ndarray] = None
        self._metadata: Optional[Dict[str, Any]] = None
        self._current_frame_index: int = 0
        self.is_loaded: bool = False
        self.filepath: Optional[str] = None

        if filepath:
            self.load_session(filepath)

    def load_session(self, filepath: str) -> bool:
        """
        Loads a data session from the specified .npz file.

        Parameters
        ----------
        filepath : str
            The path to the .npz recording file.

        Returns
        -------
        bool
            True if the session was loaded successfully, False otherwise.
        """
        print(f"Attempting to load session from: {filepath}")
        data, meta = load_recording(filepath)
        if data is not None and meta is not None:
            self._data_frames = data
            self._metadata = meta
            self._current_frame_index = 0
            self.is_loaded = True
            self.filepath = filepath
            print(f"Session loaded successfully. {self.total_frames} frames.")
            return True
        else:
            self._data_frames = None
            self._metadata = None
            self._current_frame_index = 0
            self.is_loaded = False
            self.filepath = None
            print(f"Failed to load session from: {filepath}")
            return False

    @property
    def metadata(self) -> Optional[Dict[str, Any]]:
        """Returns the metadata of the loaded session, or None if not loaded."""
        if not self.is_loaded:
            print("Warning: No session loaded. Cannot get metadata.")
        return self._metadata

    def get_next_frame(self) -> Optional[np.ndarray]:
        """
        Retrieves the next frame from the loaded session.

        Returns
        -------
        Optional[np.ndarray]
            The next data frame, or None if no more frames or no session loaded.
        """
        if not self.is_loaded or self._data_frames is None:
            # print("Warning: No session loaded. Cannot get next frame.")
            return None
        
        if self.has_more_frames():
            frame = self._data_frames[self._current_frame_index]
            self._current_frame_index += 1
            return frame
        else:
            # print("No more frames in the session.")
            return None

    def has_more_frames(self) -> bool:
        """Checks if there are more frames to replay in the current session."""
        if not self.is_loaded or self._data_frames is None:
            return False
        return self._current_frame_index < len(self._data_frames)

    def rewind(self) -> None:
        """Resets the replay to the beginning of the current session."""
        if not self.is_loaded:
            print("Warning: No session loaded. Cannot rewind.")
            return
        self._current_frame_index = 0
        print("Replayer rewound to the beginning of the session.")

    @property
    def current_frame_number(self) -> int:
        """Returns the 1-indexed number of the frame that will be returned by the next call to get_next_frame()."""
        if not self.is_loaded:
            return 0
        return self._current_frame_index + 1 # 1-indexed
    
    @property
    def total_frames(self) -> int:
        """Returns the total number of frames in the loaded session, or 0 if not loaded."""
        if not self.is_loaded or self._data_frames is None:
            return 0
        return len(self._data_frames)

if __name__ == '__main__':
    print("Running example usage of DataReplayer...")

    # --- Setup: Create a dummy recording for the replayer to use ---
    example_base_dir = "../../recordings/replayer_tests" # Adjust path if necessary
    if not os.path.exists(example_base_dir):
        os.makedirs(example_base_dir, exist_ok=True)
    print(f"Test recordings will be saved in/loaded from: {os.path.abspath(example_base_dir)}")

    recorder = DataRecorder(base_recordings_dir=example_base_dir)
    sensor_config = {'type': 'radar-XYZ', 'setting': 'outdoor'}
    recorder.start_session(sensor_configuration=sensor_config, description="Replayer test data")
    
    dummy_frames_data = []
    for i in range(3): # Create 3 frames
        frame = np.array([[i, i*2, i*3], [i*4, i*5, i*6]], dtype=np.float32)
        recorder.add_frame(frame)
        dummy_frames_data.append(frame)
    
    saved_file_path = recorder.stop_and_save_session()
    # --- End Setup ---

    if not saved_file_path:
        print("Failed to create a dummy recording for replayer test. Exiting example.")
        exit()

    print(f"\n--- Test 1: Initialize Replayer and load session {saved_file_path} ---")
    replayer = DataReplayer(filepath=saved_file_path)

    if replayer.is_loaded:
        print(f"Successfully initialized and loaded: {replayer.filepath}")
        print(f"Total frames: {replayer.total_frames}")
        meta = replayer.metadata
        if meta:
            print(f"Session Description: {meta.get('description')}")
            print(f"Sensor Config: {meta.get('sensor_configuration')}")

        print("\nReplaying frames...")
        count = 0
        while replayer.has_more_frames():
            frame_num = replayer.current_frame_number
            frame = replayer.get_next_frame()
            if frame is not None:
                count += 1
                print(f"Got frame {frame_num}/{replayer.total_frames}, Shape: {frame.shape}, Data[0,0]: {frame[0,0] if frame.size > 0 else 'N/A'}")
                # Basic check against original data (assuming order and content match)
                assert np.array_equal(frame, dummy_frames_data[frame_num-1])
        print(f"Replayed {count} frames.")
        assert count == len(dummy_frames_data)

        print("\nTest rewind...")
        replayer.rewind()
        assert replayer.current_frame_number == 1
        first_frame_after_rewind = replayer.get_next_frame()
        if first_frame_after_rewind is not None:
            print(f"First frame after rewind, Shape: {first_frame_after_rewind.shape}, Data[0,0]: {first_frame_after_rewind[0,0]}")
            assert np.array_equal(first_frame_after_rewind, dummy_frames_data[0])
        else:
            print("Failed to get frame after rewind.")

    else:
        print(f"Failed to load session into replayer.")

    print("\n--- Test 2: Load non-existent file ---")
    replayer_fail = DataReplayer()
    success = replayer_fail.load_session("non_existent_file.npz")
    assert not success
    assert not replayer_fail.is_loaded
    assert replayer_fail.get_next_frame() is None
    print("Correctly failed to load non-existent file.")
    
    print("\nDataReplayer example usage finished.") 