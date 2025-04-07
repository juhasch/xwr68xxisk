import cv2
import json
import time
import numpy as np
from pathlib import Path
from cameras import RealSenseCamera

def record_realsense_data(output_dir: str, duration: float = 10.0, device_id: str = None):
    """Record color, depth video and metadata from the RealSense camera for a specified duration.
    
    Args:
        output_dir: Directory to save the video and metadata
        duration: Recording duration in seconds
        device_id: Camera serial number (optional)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize camera with custom configuration
    camera = RealSenseCamera(device_id=device_id)
    camera.config.update({
        'width': 848,
        'height': 480,
        'fps': 30,
        'depth_enabled': True,
        'emitter_enabled': True,
        'laser_power': 360,
    })
    
    # Initialize video writers
    color_video_path = str(output_path / 'color_video.mp4')
    depth_video_path = str(output_path / 'depth_video.avi')  # AVI format for depth
    metadata_path = str(output_path / 'metadata.json')
    
    # Start camera
    camera.start()
    
    try:
        # Get first frame to initialize video writers
        first_frame = next(camera)
        height, width = first_frame['image'].shape[:2]
        
        color_fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        color_writer = cv2.VideoWriter(
            color_video_path,
            color_fourcc,
            camera.config['fps'],
            (width, height)
        )
        
        # Initialize depth writer if depth is enabled
        depth_writer = None
        if 'depth' in first_frame:
            depth_fourcc = cv2.VideoWriter_fourcc(*'XVID')
            depth_writer = cv2.VideoWriter(
                depth_video_path,
                depth_fourcc,
                camera.config['fps'],
                (width, height),
                isColor=False
            )
        
        # Store metadata for each frame
        metadata = []
        start_time = time.time()
        
        print(f"Recording for {duration} seconds from RealSense camera...")
        
        # Main recording loop
        while (time.time() - start_time) < duration:
            frame_data = next(camera)
            
            # Write color video frame
            color_writer.write(frame_data['image'])
            
            # Write depth frame if available
            if depth_writer is not None and 'depth' in frame_data:
                # Normalize depth for visualization (0-255)
                depth_image = frame_data['depth']
                normalized_depth = np.uint8(cv2.normalize(depth_image, None, 0, 255, cv2.NORM_MINMAX))
                depth_writer.write(normalized_depth)
            
            # Store metadata (excluding the image and depth arrays)
            frame_metadata = {k: v for k, v in frame_data.items() if k not in ['image', 'depth']}
            metadata.append(frame_metadata)
            
            # Display the color frame
            cv2.imshow('RealSense Color', frame_data['image'])
            
            # Display the depth frame if available
            if 'depth' in frame_data:
                # Apply colormap for better visualization
                depth_colormap = cv2.applyColorMap(normalized_depth, cv2.COLORMAP_JET)
                cv2.imshow('RealSense Depth', depth_colormap)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        # Clean up
        camera.stop()
        color_writer.release()
        if depth_writer is not None:
            depth_writer.release()
        cv2.destroyAllWindows()
        
        # Save metadata to JSON file
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
            
        print(f"Recording completed!")
        print(f"Color video saved to: {color_video_path}")
        if depth_writer is not None:
            print(f"Depth video saved to: {depth_video_path}")
        print(f"Metadata saved to: {metadata_path}")

def save_pointcloud(output_dir: str, duration: float = 3.0, device_id: str = None):
    """Capture and save a point cloud from the RealSense camera.
    
    Args:
        output_dir: Directory to save the point cloud
        duration: Time to wait before capturing (to stabilize camera)
        device_id: Camera serial number (optional)
    """
    try:
        import pyrealsense2 as rs
        import open3d as o3d
    except ImportError:
        print("Error: This function requires pyrealsense2 and open3d packages.")
        print("Install with: pip install pyrealsense2 open3d")
        return
    
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize camera
    camera = RealSenseCamera(device_id=device_id)
    camera.start()
    
    try:
        print(f"Stabilizing camera for {duration} seconds...")
        time.sleep(duration)  # Wait for camera to stabilize
        
        # Get a frame
        frame_data = next(camera)
        
        if 'depth' not in frame_data:
            print("Error: Depth data not available. Make sure depth is enabled.")
            return
        
        # Create point cloud
        print("Creating point cloud...")
        color_image = frame_data['image']
        depth_image = frame_data['depth']
        
        # Convert to Open3D format
        color_o3d = o3d.geometry.Image(color_image)
        depth_o3d = o3d.geometry.Image(depth_image)
        
        # Create RGBD image
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d, 
            depth_scale=1000.0,  # RealSense depth is in millimeters
            depth_trunc=3.0,     # Max depth in meters
            convert_rgb_to_intensity=False
        )
        
        # Create intrinsic parameters (standard for RealSense)
        width, height = color_image.shape[1], color_image.shape[0]
        intrinsic = o3d.camera.PinholeCameraIntrinsic(
            width, height,
            width / 2, height / 2,  # focal length fx, fy (simplified)
            width / 2, height / 2   # principal point cx, cy (simplified)
        )
        
        # Create point cloud
        pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, intrinsic)
        
        # Save point cloud
        pointcloud_path = str(output_path / 'pointcloud.ply')
        o3d.io.write_point_cloud(pointcloud_path, pcd)
        print(f"Point cloud saved to: {pointcloud_path}")
        
        # Visualize point cloud (optional)
        print("Visualizing point cloud... (press 'q' to exit)")
        o3d.visualization.draw_geometries([pcd])
        
    finally:
        camera.stop()

if __name__ == "__main__":
    # Example usage
    record_realsense_data(
        output_dir="realsense_recordings",
        duration=10.0,  # Record for 10 seconds
        device_id=None  # Use first available RealSense camera
    )
    
    # Uncomment to capture a point cloud
    # save_pointcloud(
    #     output_dir="realsense_pointcloud",
    #     duration=3.0,  # Wait 3 seconds for camera to stabilize
    #     device_id=None  # Use first available RealSense camera
    # ) 