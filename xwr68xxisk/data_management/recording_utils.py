import numpy as np
import datetime
from typing import Tuple, Dict, Any

def save_recording(filepath: str, data_frames: np.ndarray, metadata: Dict[str, Any]) -> None:
    """
    Saves data frames and metadata to a .npz file.

    Parameters
    ----------
    filepath : str
        The path (including filename) to save the .npz file.
    data_frames : np.ndarray
        The NumPy array containing the data frames to be saved.
        This could be a 2D array (frames x features) or 3D array (frames x rows x cols), etc.
    metadata : Dict[str, Any]
        A dictionary containing metadata to be saved.
        Recommended keys:
        - 'session_timestamp_utc': ISO format UTC timestamp string.
        - 'sensor_configuration': Dictionary or string (e.g., YAML) of sensor settings.
        - 'description': User-provided string.
        - 'frame_rate_hz': (Optional) Frame rate if applicable.
        - 'data_unit': (Optional) Unit of the data (e.g., 'ADC counts', 'meters').
    """
    try:
        np.savez_compressed(filepath, data_frames=data_frames, metadata=metadata)
        print(f"Recording saved successfully to {filepath}")
    except Exception as e:
        print(f"Error saving recording to {filepath}: {e}")
        # Potentially re-raise or handle more gracefully depending on application needs

def load_recording(filepath: str) -> Tuple[np.ndarray | None, Dict[str, Any] | None]:
    """
    Loads data frames and metadata from a .npz file.

    Parameters
    ----------
    filepath : str
        The path to the .npz file.

    Returns
    -------
    Tuple[np.ndarray | None, Dict[str, Any] | None]
        A tuple containing the data_frames (NumPy array) and metadata (dictionary).
        Returns (None, None) if loading fails.
    """
    try:
        with np.load(filepath, allow_pickle=True) as loaded_data:
            data_frames = loaded_data['data_frames']
            # Metadata is saved as a 0-d array, need to extract with .item()
            metadata = loaded_data['metadata'].item()
            if not isinstance(metadata, dict):
                print(f"Warning: Metadata in {filepath} is not a dictionary. Type: {type(metadata)}")
                # Decide on handling: return as is, or try to convert, or error out
            print(f"Recording loaded successfully from {filepath}")
            return data_frames, metadata
    except FileNotFoundError:
        print(f"Error: Recording file not found at {filepath}")
        return None, None
    except KeyError as e:
        print(f"Error: Missing expected key {e} in recording file {filepath}")
        return None, None
    except Exception as e:
        print(f"Error loading recording from {filepath}: {e}")
        return None, None

if __name__ == '__main__':
    # Example Usage
    print("Running example usage of recording utilities...")

    # Create dummy data
    example_data = np.random.rand(10, 100) # 10 frames, 100 features per frame
    example_metadata = {
        'session_timestamp_utc': datetime.datetime.utcnow().isoformat(),
        'sensor_configuration': {'mode': 'A', 'range': 50, 'power': 'max'},
        'description': 'Test recording for utility functions.',
        'frame_rate_hz': 10,
        'data_unit': 'normalized_intensity'
    }

    # Define file paths
    # Ensure 'recordings' and 'tests/test_data' directories exist for this example to run directly
    # In a real application, these paths would be handled more robustly.
    import os
    recordings_dir = "../../recordings" # Adjust path if running from xwr68xxisk/data_management
    test_data_dir = "../../tests/test_data" # Adjust path

    if not os.path.exists(recordings_dir):
        os.makedirs(recordings_dir)
    if not os.path.exists(test_data_dir):
        os.makedirs(test_data_dir)

    example_filepath_save = os.path.join(recordings_dir, "example_session.npz")
    example_filepath_load = example_filepath_save # Same file for this test

    # Test saving
    print(f"\nAttempting to save to: {os.path.abspath(example_filepath_save)}")
    save_recording(example_filepath_save, example_data, example_metadata)

    # Test loading
    print(f"\nAttempting to load from: {os.path.abspath(example_filepath_load)}")
    loaded_data, loaded_metadata = load_recording(example_filepath_load)

    if loaded_data is not None and loaded_metadata is not None:
        print("\nSuccessfully loaded data and metadata.")
        print("Shape of loaded data:", loaded_data.shape)
        print("Loaded metadata:", loaded_metadata)

        # Verify data integrity (simple check)
        if np.array_equal(example_data, loaded_data):
            print("\nData integrity check: PASSED (original and loaded data are identical).")
        else:
            print("\nData integrity check: FAILED (original and loaded data differ).")

        # Verify metadata integrity (simple check)
        # Note: Dictionary comparison can be tricky if there are nested mutable objects or float precision issues.
        # For this example, direct comparison should work.
        if example_metadata == loaded_metadata:
            print("Metadata integrity check: PASSED (original and loaded metadata are identical).")
        else:
            print("Metadata integrity check: FAILED (original and loaded metadata differ).")
            print("Original metadata:", example_metadata)
            print("Loaded metadata:", loaded_metadata)

    else:
        print("\nFailed to load data and metadata.")

    # Test loading a non-existent file
    print("\nAttempting to load a non-existent file:")
    non_existent_filepath = os.path.join(recordings_dir, "non_existent_session.npz")
    load_recording(non_existent_filepath)

    print("\nExample usage finished.") 