import sys
import time
import numpy as np
import os
import logging
from datetime import datetime
from xwr68xxisk.radar import RadarConnection
from xwr68xxisk.parse import RadarData

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

class RobustFrameTester:
    """Test the improved read_frame method with actual frame parsing."""
    
    def __init__(self, output_dir="robust_frame_test"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Statistics
        self.frames_received = 0
        self.frames_parsed = 0
        self.frames_failed = 0
        self.start_time = None
        
    def test_robust_frame_reading(self, config_path, serial_number=None):
        """Test the improved read_frame method."""
        radar = RadarConnection()
        print("Connecting to radar...")
        radar.connect(config_path, serial_number=serial_number)
        print("Configuring and starting radar...")
        radar.configure_and_start()
        print("Radar started. Testing robust frame reading...")
        print(f"Using baudrate: {radar.data_port_baudrate}")
        
        self.start_time = time.time()
        
        try:
            frame_count = 0
            while frame_count < 500:  # Test 50 frames
                result = radar.read_frame()
                if result is not None:
                    header, payload = result
                    frame_count += 1
                    self.frames_received += 1
                    
                    print(f"\n📦 Frames received {frame_count}:")
                    print(f"   Header: {header}")
                    print(f"   Payload size: {len(payload)} bytes")
                    #print(f"   First 16 bytes: {bytes(payload[:16]).hex()}")
                    continue
                    # Try to parse the frame
                    try:
                        radar_data = RadarData()
                        radar_data.parse_frame(payload)
                        
                        if radar_data.point_cloud is not None:
                            print(f"   ✅ Parsed successfully!")
                            print(f"   Points: {len(radar_data.point_cloud)}")
                            if len(radar_data.point_cloud) > 0:
                                first_point = radar_data.point_cloud[0]
                                print(f"   First point: x={first_point[0]:.2f}m, y={first_point[1]:.2f}m, z={first_point[2]:.2f}m")
                            self.frames_parsed += 1
                        else:
                            print(f"   ⚠️  No point cloud data")
                            self.frames_failed += 1
                            
                    except Exception as e:
                        print(f"   ❌ Parse error: {e}")
                        self.frames_failed += 1
                    
                    print(f"   Statistics: received={self.frames_received}, parsed={self.frames_parsed}, failed={self.frames_failed}")
                    
                else:
                    print(".", end="", flush=True)
                    time.sleep(0.1)
            
            # Print final statistics
            duration = time.time() - self.start_time
            print(f"\n\n📊 ROBUST FRAME READING TEST RESULTS:")
            print(f"   Duration: {duration:.1f}s")
            print(f"   Frames received: {self.frames_received}")
            print(f"   Frames parsed successfully: {self.frames_parsed}")
            print(f"   Frames failed to parse: {self.frames_failed}")
            print(f"   Success rate: {self.frames_parsed/self.frames_received*100:.1f}%")
            print(f"   Frame rate: {self.frames_received/duration:.1f} Hz")
            
            # Radar statistics
            print(f"\n📈 RADAR STATISTICS:")
            print(f"   Total frames: {radar.total_frames}")
            print(f"   Missed frames: {radar.missed_frames}")
            print(f"   Invalid packets: {radar.invalid_packets}")
            print(f"   Failed reads: {radar.failed_reads}")
            
        except KeyboardInterrupt:
            print("\n\nStopping test...")
        finally:
            radar.stop()
            print("Sensor stopped.")

def main(config_path, serial_number=None):
    tester = RobustFrameTester()
    tester.test_robust_frame_reading(config_path, serial_number)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python radar_debug.py <config_file> [serial_number]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    serial_number = sys.argv[2] if len(sys.argv) > 2 else None
    
    main(config_path, serial_number)
