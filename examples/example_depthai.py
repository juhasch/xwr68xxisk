import cv2
import json
import time
import numpy as np
from pathlib import Path
from cameras import DepthAICamera

def record_depthai_data(output_dir: str, duration: float = 10.0, device_id: str = None):
    """Record color, left, right, and depth streams from the DepthAI camera for a specified duration.
    
    Args:
        output_dir: Directory to save the video and metadata
        duration: Recording duration in seconds
        device_id: Camera MX ID (optional)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize camera with custom configuration
    camera = DepthAICamera(device_id=device_id)
    camera.config.update({
        'fps': 30,
        'color_width': 1080,
        'color_height': 1080,
        'color_exposure': -1,  # Auto exposure
        'isp_scale': (1, 3),   # Scale down color frames to 1/3 size
        'depth_enabled': True,
    })
    
    # Initialize video writers for each stream
    color_video_path = str(output_path / 'color_video.mp4')
    left_video_path = str(output_path / 'left_video.mp4')
    right_video_path = str(output_path / 'right_video.mp4')
    depth_video_path = str(output_path / 'depth_video.avi')  # AVI format for depth
    metadata_path = str(output_path / 'metadata.json')
    
    # Start camera
    camera.start()
    
    try:
        # Get first frame to initialize video writers
        first_frame = next(camera)
        
        # Initialize writers for each stream
        writers = {}
        
        # RGB writer
        if 'image' in first_frame:
            height, width = first_frame['image'].shape[:2]
            color_fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writers['image'] = cv2.VideoWriter(
                color_video_path,
                color_fourcc,
                camera.config['fps'],
                (width, height)
            )
        
        # Left camera writer
        if 'left' in first_frame:
            left_height, left_width = first_frame['left'].shape[:2]
            left_fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writers['left'] = cv2.VideoWriter(
                left_video_path,
                left_fourcc,
                camera.config['fps'],
                (left_width, left_height),
                isColor=False
            )
        
        # Right camera writer
        if 'right' in first_frame:
            right_height, right_width = first_frame['right'].shape[:2]
            right_fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writers['right'] = cv2.VideoWriter(
                right_video_path,
                right_fourcc,
                camera.config['fps'],
                (right_width, right_height),
                isColor=False
            )
        
        # Depth writer
        if 'depth' in first_frame:
            depth_height, depth_width = first_frame['depth'].shape[:2]
            depth_fourcc = cv2.VideoWriter_fourcc(*'XVID')
            writers['depth'] = cv2.VideoWriter(
                depth_video_path,
                depth_fourcc,
                camera.config['fps'],
                (depth_width, depth_height),
                isColor=False
            )
        
        # Store metadata for each frame
        metadata = []
        start_time = time.time()
        
        print(f"Recording for {duration} seconds from DepthAI camera...")
        print(f"Streams: {', '.join(first_frame.keys() - {'timestamp', 'fps', 'width', 'height', 'exposure', 'iso'})}")
        
        # Main recording loop
        while (time.time() - start_time) < duration:
            frame_data = next(camera)
            
            # Write video frames for each stream
            for stream_name, writer in writers.items():
                if stream_name in frame_data:
                    # Get the frame
                    frame = frame_data[stream_name]
                    
                    # For depth, normalize for visualization
                    if stream_name == 'depth':
                        frame = np.uint8(cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX))
                    
                    # Write the frame
                    writer.write(frame)
            
            # Store metadata (excluding the image arrays)
            frame_metadata = {k: v for k, v in frame_data.items() 
                            if k not in ['image', 'left', 'right', 'depth']}
            metadata.append(frame_metadata)
            
            # Display the frames (with appropriate sizing)
            if 'image' in frame_data:
                cv2.imshow('RGB Camera', frame_data['image'])
            
            if 'left' in frame_data:
                cv2.imshow('Left Camera', frame_data['left'])
            
            if 'right' in frame_data:
                cv2.imshow('Right Camera', frame_data['right'])
            
            if 'depth' in frame_data:
                # Apply colormap for better depth visualization
                depth_colormap = cv2.applyColorMap(
                    np.uint8(cv2.normalize(frame_data['depth'], None, 0, 255, cv2.NORM_MINMAX)), 
                    cv2.COLORMAP_JET
                )
                cv2.imshow('Depth', depth_colormap)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        # Clean up
        camera.stop()
        for writer in writers.values():
            writer.release()
        cv2.destroyAllWindows()
        
        # Save metadata to JSON file
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"Recording completed!")
        for stream, writer in writers.items():
            video_path = eval(f"{stream}_video_path")
            print(f"{stream.capitalize()} video saved to: {video_path}")
        print(f"Metadata saved to: {metadata_path}")

def spatialviewer(device_id: str = None):
    """Live viewer for DepthAI camera showing all streams and 3D spatial data.
    
    Args:
        device_id: Camera MX ID (optional)
    """
    try:
        # Initialize camera
        camera = DepthAICamera(device_id=device_id)
        camera.config.update({
            'fps': 30,
            'depth_enabled': True,
            'lrcheck': True,  # Better depth quality
            'subpixel': True, # Better depth quality
        })
        
        camera.start()
        
        print("DepthAI Spatial Viewer")
        print("Press 'q' to quit")
        
        while True:
            # Get frame data
            frame_data = next(camera)
            
            # Display frames
            displays = []
            
            # Display RGB
            if 'image' in frame_data:
                rgb = frame_data['image']
                cv2.putText(rgb, "RGB", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                displays.append(rgb)
            
            # Display mono cameras
            mono_displays = []
            if 'left' in frame_data:
                left = cv2.cvtColor(frame_data['left'], cv2.COLOR_GRAY2BGR)
                cv2.putText(left, "LEFT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                mono_displays.append(left)
                
            if 'right' in frame_data:
                right = cv2.cvtColor(frame_data['right'], cv2.COLOR_GRAY2BGR)
                cv2.putText(right, "RIGHT", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                mono_displays.append(right)
            
            # Combine mono displays horizontally
            if mono_displays:
                # Ensure both are the same size
                if len(mono_displays) > 1:
                    h, w = mono_displays[0].shape[:2]
                    mono_displays = [cv2.resize(img, (w, h)) for img in mono_displays]
                    mono_combined = np.hstack(mono_displays)
                else:
                    mono_combined = mono_displays[0]
                displays.append(mono_combined)
            
            # Display depth
            if 'depth' in frame_data:
                # Normalize and colormap depth
                depth_colormap = cv2.applyColorMap(
                    np.uint8(cv2.normalize(frame_data['depth'], None, 0, 255, cv2.NORM_MINMAX)), 
                    cv2.COLORMAP_JET
                )
                cv2.putText(depth_colormap, "DEPTH", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                displays.append(depth_colormap)
            
            # Combine all displays vertically
            if displays:
                # Resize to consistent width
                target_width = 640
                resized_displays = []
                for display in displays:
                    h, w = display.shape[:2]
                    new_h = int(h * (target_width / w))
                    resized = cv2.resize(display, (target_width, new_h))
                    resized_displays.append(resized)
                
                combined_display = np.vstack(resized_displays)
                cv2.imshow("DepthAI Spatial Viewer", combined_display)
            
            # Process key events
            key = cv2.waitKey(1)
            if key == ord('q'):
                break
                
    finally:
        camera.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Example usage
    record_depthai_data(
        output_dir="depthai_recordings",
        duration=10.0,  # Record for 10 seconds
        device_id=None  # Use first available DepthAI camera
    )
    
    # Uncomment to start the spatial viewer
    # spatialviewer(device_id=None) 