import sys
import time
import numpy as np
import os
import logging
import struct
from datetime import datetime
from xwr68xxisk.radar import RadarConnection
from xwr68xxisk.parse import RadarData

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

class RobustFrameTester:
    """Test robust frame reading with proper TLV parsing."""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.radar = None
        self.frames_received = 0
        self.frames_parsed = 0
        self.frames_failed = 0
        self.last_frame_time = None
        
    def run_test(self, duration: float = 5.0):
        """Run the robust frame reading test."""
        print("Connecting to radar...")
        self.radar = RadarConnection()
        
        try:
            self.radar.connect(self.config_file)
            print("Configuring and starting radar...")
            self.radar.configure_and_start()
            print("Radar started. Testing robust frame reading...")
            print(f"Using baudrate: {self.radar.data_port_baudrate}")
            
            start_time = time.time()
            last_stats_time = start_time
            
            tmp_radar_data = RadarData()

            while time.time() - start_time < duration:
                print(time.time() - start_time < duration)
                try:
                    # Read frame using the robust read_frame method
                    frame_data = self.radar.read_frame()
                    
                    if frame_data is None:
                        continue
                        
                    header, payload = frame_data
                    if header is None or payload is None:
                        continue
                    
                    self.frames_received += 1
                    current_time = time.time()
                    
                    # Calculate time since last frame
                    if self.last_frame_time is not None:
                        time_since_last = current_time - self.last_frame_time
                    else:
                        time_since_last = 0.0
                    
                    self.last_frame_time = current_time
                    

                    self.radar.cli_port = None
                    # Parse the frame using the proper RadarData class
                    try:
                        # Create RadarData object with the current frame
                        #radar_data = RadarData()
                        waiting = self.radar.data_port.in_waiting
                        print(f"waiting: {waiting}")
                        tmp_radar_data.radar_connection.data_port.read(waiting)
                        
                        continue

                        radar_data.frame_number = header.get('frame_number')
                        radar_data.num_tlvs = header.get('num_tlvs', 0)
                        radar_data.config_params = self.radar.radar_params
                        
                        # Parse TLV data using the existing parse.py implementation
                        radar_data._parse_tlv_data(payload)
                        
                        # Display frame information
                        print(f"\n📦 Frames received {self.frames_received}:")
                        print(f"   Header: {header}")
                        print(f"   Payload size: {len(payload)} bytes")
#                        print(f"   Time since last frame: {time_since_last:.3f}s")
                        
                        # Display parsed TLV data
#                        print(f"   ✅ TLV parsing successful!")
#                        print(f"   Number of TLVs: {radar_data.num_tlvs}")
                        
                        # Display point cloud data if available
                        # if radar_data.pc and len(radar_data.pc[0]) > 0:
                        #     x, y, z, v = radar_data.pc
                        #     print(f"   Point cloud: {len(x)} points")
                        #     if len(x) > 0:
                        #         print(f"   First 3 points:")
                        #         for i in range(min(3, len(x))):
                        #             print(f"     Point {i+1}: x={x[i]:.2f}m, y={y[i]:.2f}m, z={z[i]:.2f}m, v={v[i]:.2f}m/s")
                        
                        # Display range profile data if available
                        if radar_data.adc is not None and len(radar_data.adc) > 0:
                            print(f"   Range profile: {len(radar_data.adc)} bins")
                            print(f"   Range values: min={radar_data.adc.min()}, max={radar_data.adc.max()}, mean={radar_data.adc.mean():.2f}")
                        
                        # Display stats data if available
                        if radar_data.stats_data is not None:
                            print(f"   Stats data available: {len(radar_data.stats_data)} bytes")
                        
                        # Display temperature stats if available
                        if radar_data.temperature_stats_data is not None:
                            print(f"   Temperature stats available: {len(radar_data.temperature_stats_data)} bytes")
                        
                        self.frames_parsed += 1
                        
                    except Exception as parse_error:
                        print(f"   ❌ TLV parse error: {parse_error}")
                        self.frames_failed += 1
                    
                    # Print statistics every 10 seconds
                    if current_time - last_stats_time >= 11.0:
                        elapsed = current_time - start_time
                        frame_rate = self.frames_received / elapsed if elapsed > 0 else 0
                        success_rate = (self.frames_parsed / self.frames_received * 100) if self.frames_received > 0 else 0
                        
                        print(f"\n📊 Statistics: received={self.frames_received}, parsed={self.frames_parsed}, failed={self.frames_failed}")
                        print(f"   Frame rate: {frame_rate:.1f} Hz, Success rate: {success_rate:.1f}%")
                        last_stats_time = current_time
                    
                    time.sleep(0.001)  # Small delay to prevent overwhelming
                    
                except KeyboardInterrupt:
                    print("\nTest interrupted by user")
                    break
                except Exception as e:
                    print(f"Error during frame reading: {e}")
                    continue
            
            # Final statistics
            elapsed = time.time() - start_time
            frame_rate = self.frames_received / elapsed if elapsed > 0 else 0
            success_rate = (self.frames_parsed / self.frames_received * 100) if self.frames_received > 0 else 0
            
            print(f"\n📊 ROBUST FRAME READING TEST RESULTS:")
            print(f"   Duration: {elapsed:.1f}s")
            print(f"   Frames received: {self.frames_received}")
            print(f"   Frames parsed successfully: {self.frames_parsed}")
            print(f"   Frames failed to parse: {self.frames_failed}")
            print(f"   Success rate: {success_rate:.1f}%")
            print(f"   Frame rate: {frame_rate:.1f} Hz")
            
            print(f"\n📈 RADAR STATISTICS:")
            print(f"   Total frames: {self.radar.total_frames}")
            print(f"   Missed frames: {self.frames_received - self.radar.total_frames}")
            print(f"   Invalid packets: {self.frames_failed}")
            print(f"   Failed reads: {self.frames_received - self.frames_parsed - self.frames_failed}")
            
        finally:
            if self.radar:
                self.radar.stop()
                print("Sensor stopped.")

def main():
    if len(sys.argv) != 2:
        print("Usage: python radar_debug.py <config_file>")
        sys.exit(1)
    
    config_file = sys.argv[1]
    
    if not os.path.exists(config_file):
        print(f"Config file not found: {config_file}")
        sys.exit(1)
    
    tester = RobustFrameTester(config_file)
    tester.run_test(duration=120)  # Shorter test duration

if __name__ == "__main__":
    main()
