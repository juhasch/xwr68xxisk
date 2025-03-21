import cv2
import json
import time
from pathlib import Path
from cameras import OpenCVCamera

def record_camera_data(output_dir: str, duration: float = 10.0, device_id: int = 0):
    """Record video and metadata from the camera for a specified duration.
    
    Args:
        output_dir: Directory to save the video and metadata
        duration: Recording duration in seconds
        device_id: Camera device ID
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize camera with custom configuration
    camera = OpenCVCamera(device_id=device_id)
    camera.config.update({
        'width': 1280,
        'height': 720,
        'fps': 30,
        'autofocus': True,
    })
    
    # Initialize video writer
    video_path = str(output_path / 'recorded_video.mp4')
    metadata_path = str(output_path / 'metadata.json')
    
    # Start camera
    camera.start()
    
    try:
        # Get first frame to initialize video writer
        first_frame = next(camera)
        height, width = first_frame['image'].shape[:2]
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        video_writer = cv2.VideoWriter(
            video_path,
            fourcc,
            camera.config['fps'],
            (width, height)
        )
        
        # Store metadata for each frame
        metadata = []
        start_time = time.time()
        
        print(f"Recording for {duration} seconds...")
        
        # Main recording loop
        while (time.time() - start_time) < duration:
            frame_data = next(camera)
            
            # Write video frame
            video_writer.write(frame_data['image'])
            
            # Store metadata (excluding the image array)
            frame_metadata = {k: v for k, v in frame_data.items() if k != 'image'}
            metadata.append(frame_metadata)
            
            # Display the frame (optional)
            cv2.imshow('Recording', frame_data['image'])
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        # Clean up
        camera.stop()
        video_writer.release()
        cv2.destroyAllWindows()
        
        # Save metadata to JSON file
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"Recording completed!")
        print(f"Video saved to: {video_path}")
        print(f"Metadata saved to: {metadata_path}")

if __name__ == "__main__":
    # Example usage
    record_camera_data(
        output_dir="camera_recordings",
        duration=10.0,  # Record for 10 seconds
        device_id=0     # Use default camera
    ) 