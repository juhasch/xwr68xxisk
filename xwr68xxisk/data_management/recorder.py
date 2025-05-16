import numpy as np
from datetime import datetime, UTC
import os
import uuid
from typing import Dict, Any, List, Optional, Tuple

from .recording_utils import save_recording

class DataRecorder:
    """
    Manages the recording of data frames into sessions and saves them to .npz files.
    """
    def __init__(self, base_recordings_dir: str, initial_session_metadata: Optional[Dict[str, Any]] = None):
        """
        Initializes the DataRecorder.

        Parameters
        ----------
        base_recordings_dir : str
            The base directory where session recordings will be saved.
        initial_session_metadata : Optional[Dict[str, Any]], optional
            Metadata to be included with every session, by default None.
        """
        self.base_recordings_dir = base_recordings_dir
        os.makedirs(self.base_recordings_dir, exist_ok=True)
        self.initial_session_metadata = initial_session_metadata if initial_session_metadata else {}

        self.current_session_id: Optional[str] = None
        self.session_start_time_utc: Optional[datetime] = None
        self.frames_buffer: List[np.ndarray] = []
        self.session_metadata: Dict[str, Any] = {}
        self.is_recording: bool = False

    def start_session(self, sensor_configuration: Dict[str, Any], description: str = "Recording session") -> None:
        """
        Starts a new recording session.

        Any previously unsaved session data will be lost.

        Parameters
        ----------
        sensor_configuration : Dict[str, Any]
            Configuration of the sensor at the start of the session.
        description : str, optional
            A description for this recording session, by default "Recording session".
        """
        if self.is_recording:
            print("Warning: A session is already active. Stopping it and starting a new one.")
            # Potentially save the old one or give a more specific warning/error
            self.frames_buffer = [] # Clear buffer for the new session

        self.current_session_id = str(uuid.uuid4())
        self.session_start_time_utc = datetime.now(UTC)
        self.frames_buffer = []
        self.session_metadata = {
            **self.initial_session_metadata, # Start with recorder-level initial metadata
            'session_id': self.current_session_id,
            'session_timestamp_utc': self.session_start_time_utc.isoformat(),
            'sensor_configuration': sensor_configuration,
            'description': description
        }
        self.is_recording = True
        print(f"Session {self.current_session_id} started at {self.session_start_time_utc.isoformat()} UTC.")

    def add_frame(self, frame_data: np.ndarray) -> None:
        """
        Adds a data frame to the current recording session.

        Parameters
        ----------
        frame_data : np.ndarray
            The data frame to add.
        """
        if not self.is_recording or self.current_session_id is None:
            print("Warning: No active recording session. Frame not added. Call start_session() first.")
            return
        self.frames_buffer.append(frame_data)
        # print(f"Frame added to session {self.current_session_id}. Total frames: {len(self.frames_buffer)}")

    def stop_and_save_session(self, final_description: Optional[str] = None, additional_metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Stops the current recording session, saves the data, and resets the recorder state.

        Parameters
        ----------
        final_description : Optional[str], optional
            An updated description for the session. If None, the initial description is kept.
        additional_metadata : Optional[Dict[str, Any]], optional
            Any additional metadata to merge into the session's metadata before saving.

        Returns
        -------
        Optional[str]
            The filepath of the saved recording, or None if saving failed or no data.
        """
        if not self.is_recording or self.current_session_id is None:
            print("No active session to stop or save.")
            return None

        if not self.frames_buffer:
            print(f"No frames recorded in session {self.current_session_id}. Nothing to save.")
            self.is_recording = False
            self.current_session_id = None
            return None

        # Combine frames into a single NumPy array
        try:
            all_frames_array = np.stack(self.frames_buffer)
        except ValueError as e:
            print(f"Error stacking frames: {e}. Frames might have inconsistent shapes. Cannot save.")
            # Potentially try np.array(self.frames_buffer, dtype=object) if shapes are truly variable and acceptable
            self.is_recording = False # Reset state even on failure to stack
            self.current_session_id = None
            self.frames_buffer = []
            return None

        # Prepare final metadata
        final_meta = self.session_metadata.copy()
        if final_description is not None:
            final_meta['description'] = final_description
        if additional_metadata:
            final_meta.update(additional_metadata)
        
        final_meta['frame_count'] = len(self.frames_buffer)
        if self.session_start_time_utc:
            session_duration = datetime.now(UTC) - self.session_start_time_utc
            final_meta['session_duration_seconds'] = session_duration.total_seconds()

        # Generate filename
        timestamp_str = self.session_start_time_utc.strftime("%Y%m%d_%H%M%S")
        filename = f"session_{self.current_session_id}_{timestamp_str}.npz"
        filepath = os.path.join(self.base_recordings_dir, filename)

        # Save using the utility function
        print(f"Stopping session {self.current_session_id}. Attempting to save {len(self.frames_buffer)} frames to {filepath}...")
        save_recording(filepath, all_frames_array, final_meta)
        # save_recording returns None, success is indicated by print from save_recording and no exception

        # Reset session state
        self.frames_buffer = []
        self.is_recording = False
        self.current_session_id = None
        self.session_metadata = {}
        self.session_start_time_utc = None

        return filepath

    def get_session_duration(self):
        session_duration = datetime.now(UTC) - self.session_start_time_utc
        return session_duration

if __name__ == '__main__':
    print("Running example usage of DataRecorder...")

    # Ensure the base directory for recordings exists
    # For example, create it in the parent directory relative to this script's location
    # Adjust path as needed if this script moves
    example_base_dir = "../../recordings/recorder_tests"
    if not os.path.exists(example_base_dir):
        os.makedirs(example_base_dir, exist_ok=True)
    print(f"Test recordings will be saved in: {os.path.abspath(example_base_dir)}")

    # 1. Initialize recorder
    initial_meta = {'recorder_version': '1.0', 'site_location': 'lab_A'}
    recorder = DataRecorder(base_recordings_dir=example_base_dir, initial_session_metadata=initial_meta)

    # 2. Start a session
    sensor_config_session1 = {'mode': 'ranging', 'power_level': 10, 'frequency_ghz': 60.5}
    recorder.start_session(sensor_configuration=sensor_config_session1, description="First test session with dummy data")

    # 3. Add some frames
    for i in range(5):
        # Each frame is a 2x3 array for this example
        frame = np.random.rand(2, 3) * (i + 1)
        recorder.add_frame(frame)
        print(f"Added frame {i+1} to session {recorder.current_session_id}")
        # time.sleep(0.1) # Simulate time between frames

    # 4. Stop and save the session
    saved_filepath1 = recorder.stop_and_save_session(additional_metadata={'quality_check': 'passed'})
    if saved_filepath1:
        print(f"Session 1 saved to: {saved_filepath1}")
        # Optionally, load and verify
        from .recording_utils import load_recording
        data, meta = load_recording(saved_filepath1)
        if data is not None:
            print(f"Verified loading: {data.shape} frames, metadata keys: {list(meta.keys())}")
            assert data.shape[0] == 5 # We added 5 frames
            assert meta['recorder_version'] == '1.0'
            assert meta['quality_check'] == 'passed'

    print("\n--- Second Session Example (no frames) ---")
    # 5. Start another session
    sensor_config_session2 = {'mode': 'doppler', 'power_level': 5, 'sample_rate_hz': 1000}
    recorder.start_session(sensor_configuration=sensor_config_session2, description="Empty session test")

    # 6. Stop without adding frames
    saved_filepath2 = recorder.stop_and_save_session()
    if saved_filepath2:
        print(f"Session 2 saved to: {saved_filepath2} (this should not happen for empty session)")
    else:
        print("Session 2 correctly not saved as it was empty.")

    print("\n--- Third Session Example (add frame without start) ---")
    # 7. Try adding a frame without starting a session (after recorder reset from previous stop)
    # For this to accurately test, ensure recorder state is fully reset if stop_and_save_session wasn't called or failed partially.
    # Current implementation resets state in stop_and_save_session.
    # If we create a new recorder instance, it will be fresh.
    new_recorder = DataRecorder(base_recordings_dir=example_base_dir)
    new_recorder.add_frame(np.random.rand(1,1)) # Should print warning

    print("\nDataRecorder example usage finished.") 