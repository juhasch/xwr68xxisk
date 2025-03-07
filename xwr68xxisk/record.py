"""Record radar data from the sensor and save it to a file."""

import os
import time
import numpy as np
from typing import Tuple, List, Optional
from datetime import datetime

from xwr68xxisk.radar import RadarConnection, create_radar, RadarConnectionError
from xwr68xxisk.parse import RadarData

RUNNER_CI = True if os.getenv("CI") == "true" else False


def main(serial_number: Optional[str] = None):
    # Create recordings directory if it doesn't exist
    recording_dir = "recordings"
    os.makedirs(recording_dir, exist_ok=True)

    # Create output file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(recording_dir, f"radar_data_{timestamp}.csv")
    recording_file = open(filename, "w")
    
    # Write CSV header
    recording_file.write("frame,x,y,velocity,snr\n")
      
    print("Starting radar")

    radar_base = RadarConnection()
    radar_type, config_file = radar_base.detect_radar_type()
    if not radar_type:
        raise RadarConnectionError("No supported radar detected")
    
    print(f"Creating {radar_type} radar instance")
    radar = create_radar(radar_type)            
    radar.connect(config_file)

    if radar.version_info:
        formatted_info = '\n'.join(str(line) for line in radar.version_info)
        print(formatted_info)

    radar.configure_and_start()

    try:
        print(f"Recording data to {filename}")
        print("Press Ctrl+C to stop recording")
        
        frame_count = 0
        no_data_count = 0
        max_no_data = 10  # Maximum number of consecutive frames with no data
        total_points = 0
        start_time = time.time()
        last_status_update = time.time()
        
        while True:
            # Check for data with a short timeout
            data = RadarData(radar)
            
            if data is not None and data.pc is not None:
                x, y, z, velocity = data.pc
                frame_number = data.frame_number if data.frame_number is not None else frame_count
                
                # Update statistics
                total_points += len(x)
                elapsed_time = time.time() - start_time
                points_per_second = total_points / elapsed_time if elapsed_time > 0 else 0
                
                # Print status update (overwrite previous line)
                print(f"\rFrame: {frame_number}, Points: {len(x)}, Total: {total_points}, Rate: {points_per_second:.1f} pts/s    ", end="", flush=True)
                last_status_update = time.time()
                
                # Get SNR values, use default if not available
                if data.snr and len(data.snr) == len(x):
                    snr_values = np.array(data.snr)
                else:
                    snr_values = np.ones(len(x)) * 30

                # Write data points to CSV
                    for i in range(len(x)):
                        recording_file.write(f"{frame_number},{x[i]:.3f},{y[i]:.3f},{velocity[i]:.3f},{snr_values[i]:.3f}\n")
                    #recording_file.flush()  # Ensure data is written to disk
                
                frame_count += 1
                no_data_count = 0  # Reset no data counter on successful frame
            else:
                no_data_count += 1
                current_time = time.time()
                
                # Update status message every second
                if current_time - last_status_update >= 1.0:
                    print("\rWaiting for data...", end="", flush=True)
                    last_status_update = current_time
                
                if no_data_count >= max_no_data:
                    print("\nNo data received from radar for too long. Please check the connection and configuration.")
                    break
                
            time.sleep(0.1)  # Wait a bit longer when no data is received
                    
    except KeyboardInterrupt:
        print("\nRecording stopped by user")
    finally:
        recording_file.close()
        radar.close()
        
        # Print final statistics
        elapsed_time = time.time() - start_time
        print(f"\nRecording completed:")
        print(f"Total frames: {frame_count}")
        print(f"Total points: {total_points}")
        print(f"Average points per frame: {total_points/frame_count:.1f}" if frame_count > 0 else "No frames recorded")
        print(f"Average points per second: {total_points/elapsed_time:.1f}" if elapsed_time > 0 else "No time elapsed")
        print(f"Data saved to: {filename}")

if __name__ == "__main__":
    main() 