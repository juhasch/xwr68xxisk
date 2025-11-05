# ROS2 Radar Point Cloud Publisher

This section describes the ROS2 integration for the TI mmWave radar sensors (XWR68xx series).

## Overview

The ROS2 radar node publishes radar data using two separate topics:
1. **Point Cloud Data** - High-frequency data containing detected points with position, velocity, and signal quality
2. **Radar Configuration** - Low-frequency data containing static radar configuration and sensor information

This separation provides better bandwidth efficiency and follows ROS2 best practices for sensor data publishing.

## Message Formats

### 1. RadarPointCloud.msg (High-frequency topic: `radar_point_cloud`)

Contains dynamic point cloud data that changes with each radar frame:

#### Header Information
- `std_msgs/Header header` - Standard ROS header with timestamp and frame_id
- `uint32 frame_number` - Frame sequence number from radar
- `uint32 num_points` - Number of detected points in this frame

#### Point Cloud Data (all arrays have same length = num_points)

**Position Data (Cartesian coordinates):**
- `float32[] x` - X coordinates in meters (forward from radar)
- `float32[] y` - Y coordinates in meters (right from radar)
- `float32[] z` - Z coordinates in meters (up from radar)

**Spherical Coordinates (native radar measurements):**
- `float32[] range` - Distance from radar in meters
- `float32[] azimuth` - Horizontal angle in radians (-π to π)
- `float32[] elevation` - Vertical angle in radians (-π/2 to π/2)

**Velocity Data:**
- `float32[] velocity` - Radial velocity in m/s (positive = moving away)

**Signal Quality Metrics:**
- `float32[] snr` - Signal-to-noise ratio in dB
- `float32[] rcs` - Radar cross-section in dBsm (decibels relative to square meter)

**Additional Data (optional):**
- `float32[] noise` - Noise level in dB (if available)
- `uint16[] doppler_bin` - Doppler bin index (if available)
- `float32[] intensity` - Signal intensity in arbitrary units (if available)

### 2. RadarInfo.msg (Low-frequency topic: `radar_info`)

Contains static radar configuration and sensor information:

#### Sensor Identification
- `string sensor_model` - Radar sensor model (e.g., "XWR68xx")
- `string firmware_version` - Firmware version
- `string serial_number` - Sensor serial number

#### Current Status
- `uint8 sensor_status` - Overall sensor status (0=OK, 1=WARNING, 2=ERROR)
- `string sensor_info` - Additional sensor information/warnings
- `bool is_connected` - Whether radar is connected
- `bool is_streaming` - Whether radar is actively streaming data

#### Configuration Parameters
- `float32 carrier_frequency_ghz` - Carrier frequency in GHz
- `float32 bandwidth_mhz` - Bandwidth in MHz
- `float32 frame_period_ms` - Frame period in milliseconds
- `uint32 num_tx_antennas` - Number of TX antennas
- `uint32 num_rx_antennas` - Number of RX antennas

#### Measurement Capabilities
- `float32 range_resolution` - Range resolution in meters
- `float32 velocity_resolution` - Velocity resolution in m/s
- `float32 max_range` - Maximum unambiguous range in meters
- `float32 max_velocity` - Maximum unambiguous velocity in m/s
- Field of view limits (azimuth_fov_min/max, elevation_fov_min/max)

#### Signal Processing Configuration
- `bool clutter_removal_enabled` - Whether static clutter removal is enabled
- `bool multi_object_beamforming` - Whether multi-object beamforming is enabled
- `float32 cfar_threshold` - CFAR detection threshold

## Installation

### Prerequisites

1. **ROS2 Environment:**
   ```bash
   # Source ROS2 (adjust for your ROS2 distribution)
   source /opt/ros/humble/setup.bash
   ```

2. **Python Dependencies:**
   ```bash
   pip install numpy pyserial pyyaml
   ```

### Building the Package

1. **Clone the repository:**
   ```bash
   cd ~/ros2_ws/src
   git clone https://github.com/juhasch/xwr68xxisk.git
   ```

2. **Build the package:**
   ```bash
   cd ~/ros2_ws
   colcon build --packages-select xwr68xxisk
   source install/setup.bash
   ```

## Usage

### Basic Usage

1. **Launch the radar publisher node:**
   ```bash
   ros2 launch xwr68xxisk radar_publisher.launch.py
   ```

2. **View published topics:**
   ```bash
   ros2 topic list
   # You should see:
   # /radar_point_cloud
   # /radar_info
   ```

3. **Monitor point cloud data:**
   ```bash
   ros2 topic echo /radar_point_cloud
   ```

4. **Check radar configuration:**
   ```bash
   ros2 topic echo /radar_info
   ```

### Advanced Usage

**Using a specific radar profile:**
```bash
ros2 launch xwr68xxisk radar_publisher.launch.py radar_profile:=/path/to/profile.cfg
```

**Custom publish rates:**
```bash
ros2 launch xwr68xxisk radar_publisher.launch.py \
  publish_rate:=20.0 \
  radar_info_publish_rate:=0.5
```

### Replaying Recorded Data (Testing)

For testing and development without physical radar hardware, you can replay recorded data from CSV and YAML files:

1. **Basic replay with default recording:**
   ```bash
   ros2 launch xwr68xxisk radar_replay.launch.py
   ```

2. **Replay specific recording:**
   ```bash
   ros2 launch xwr68xxisk radar_replay.launch.py \
     recording_directory:=/path/to/recordings \
     base_filename:=radar_data_20250517_134646
   ```

3. **Replay with different timing modes:**
   ```bash
   # Half speed replay using original timestamps
   ros2 launch xwr68xxisk radar_replay.launch.py \
     use_original_timestamps:=true \
     time_scale_factor:=0.5

   # Double speed replay
   ros2 launch xwr68xxisk radar_replay.launch.py \
     use_original_timestamps:=true \
     time_scale_factor:=2.0

   # Fixed rate replay (ignore original timing)
   ros2 launch xwr68xxisk radar_replay.launch.py \
     replay_rate_hz:=20.0 \
     loop_replay:=false
   ```

4. **Available replay parameters:**
   - `recording_directory`: Directory containing CSV and YAML files
   - `base_filename`: Base filename without extension
   - `replay_rate_hz`: Fixed replay rate when not using original timestamps
   - `loop_replay`: Whether to loop continuously (default: true)
   - `use_original_timestamps`: Use timing from recording (default: false)
   - `time_scale_factor`: Speed multiplier for original timestamps (default: 1.0)

**Using parameter file:**
```bash
ros2 run xwr68xxisk radar_publisher_node.py --ros-args --params-file config/radar_publisher_params.yaml
```

### Node Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `radar_profile` | string | "" | Path to radar profile configuration file |
| `frame_id` | string | "radar_link" | TF frame ID for the radar sensor |
| `publish_rate` | double | 10.0 | Point cloud publishing rate in Hz |
| `radar_info_publish_rate` | double | 1.0 | Radar info publishing rate in Hz |
| `auto_connect` | bool | true | Automatically connect to radar on startup |
| `radar_info_topic` | string | "radar_info" | Topic name for radar info messages |

## Data Analysis Examples

### Working with Point Cloud Data

**Python subscriber example:**
```python
import rclpy
from rclpy.node import Node
from xwr68xxisk.msg import RadarPointCloud, RadarInfo
import numpy as np

class RadarAnalyzer(Node):
    def __init__(self):
        super().__init__('radar_analyzer')
        
        # Subscribe to both topics
        self.pc_subscription = self.create_subscription(
            RadarPointCloud, 'radar_point_cloud', self.point_cloud_callback, 10)
        self.info_subscription = self.create_subscription(
            RadarInfo, 'radar_info', self.radar_info_callback, 10)
        
        self.radar_config = None
    
    def radar_info_callback(self, msg):
        """Store radar configuration info."""
        self.radar_config = msg
        self.get_logger().info(f'Radar config updated: {msg.sensor_model}, '
                              f'Frame period: {msg.frame_period_ms}ms')
    
    def point_cloud_callback(self, msg):
        """Process point cloud data."""
        if len(msg.x) == 0:
            return
            
        # Convert to numpy arrays
        x = np.array(msg.x)
        y = np.array(msg.y)
        z = np.array(msg.z)
        velocity = np.array(msg.velocity)
        snr = np.array(msg.snr)
        rcs = np.array(msg.rcs)
        
        # Analyze data
        distances = np.sqrt(x**2 + y**2 + z**2)
        
        self.get_logger().info(
            f"Frame {msg.frame_number}: {len(x)} points\n"
            f"  Range: {distances.min():.2f} - {distances.max():.2f} m\n"
            f"  Velocity: {velocity.min():.2f} - {velocity.max():.2f} m/s\n"
            f"  SNR: {snr.min():.1f} - {snr.max():.1f} dB"
        )
        
        # Filter points by SNR threshold
        high_snr_mask = snr > 15.0
        if np.any(high_snr_mask):
            self.get_logger().info(f"  High-quality points: {np.sum(high_snr_mask)}")

def main():
    rclpy.init()
    node = RadarAnalyzer()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

### Message Rate Monitoring

```bash
# Monitor point cloud message rate
ros2 topic hz /radar_point_cloud

# Monitor radar info message rate
ros2 topic hz /radar_info

# Check message sizes
ros2 topic bw /radar_point_cloud
ros2 topic bw /radar_info
```

### Data Recording and Playback

**Record radar data:**
```bash
ros2 bag record /radar_point_cloud /radar_info
```

**Playback recorded data:**
```bash
ros2 bag play <bag_file>
```

## Coordinate Systems

### Radar Coordinate System
- **X-axis:** Forward from radar (positive = in front)
- **Y-axis:** Right from radar (positive = to the right)  
- **Z-axis:** Up from radar (positive = upward)

### Angular Measurements
- **Azimuth:** Horizontal angle from X-axis (-π to π radians)
- **Elevation:** Vertical angle from XY-plane (-π/2 to π/2 radians)

## Integration with Other ROS2 Packages

### TF2 Integration

```xml
<launch>
  <node pkg="tf2_ros" exec="static_transform_publisher" 
        args="0 0 0.5 0 0 0 base_link radar_link"/>
  <include file="$(find-pkg-share xwr68xxisk)/launch/radar_publisher.launch.py"/>
</launch>
```

### Convert to Standard PointCloud2

```python
from sensor_msgs.msg import PointCloud2, PointField
import struct

def convert_to_pointcloud2(radar_msg):
    """Convert RadarPointCloud to standard PointCloud2."""
    cloud_msg = PointCloud2()
    cloud_msg.header = radar_msg.header
    cloud_msg.height = 1
    cloud_msg.width = radar_msg.num_points
    
    # Define fields including radar-specific data
    fields = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name='velocity', offset=12, datatype=PointField.FLOAT32, count=1),
        PointField(name='snr', offset=16, datatype=PointField.FLOAT32, count=1),
        PointField(name='rcs', offset=20, datatype=PointField.FLOAT32, count=1),
    ]
    
    cloud_msg.fields = fields
    cloud_msg.point_step = 24
    cloud_msg.row_step = cloud_msg.point_step * cloud_msg.width
    cloud_msg.is_dense = True
    
    # Pack data
    data = []
    for i in range(radar_msg.num_points):
        data.append(struct.pack('ffffff', 
                               radar_msg.x[i], radar_msg.y[i], radar_msg.z[i],
                               radar_msg.velocity[i], radar_msg.snr[i], radar_msg.rcs[i]))
    
    cloud_msg.data = b''.join(data)
    return cloud_msg
```

## Troubleshooting

### Common Issues

1. **No radar detected:**
   - Check USB connection and user permissions for serial ports
   - Add user to dialout group: `sudo usermod -a -G dialout $USER`

2. **Node fails to start:**
   - Check ROS2 environment: `ros2 interface list | grep xwr68xxisk`
   - Verify message compilation: `ros2 interface show xwr68xxisk/msg/RadarPointCloud`

3. **No data published:**
   - Check radar connection status in radar_info topic
   - Verify radar profile configuration

### Debug Commands

```bash
# Check if messages are available
ros2 interface show xwr68xxisk/msg/RadarPointCloud
ros2 interface show xwr68xxisk/msg/RadarInfo

# Monitor node status
ros2 node info /radar_publisher_node

# Check topic information
ros2 topic info /radar_point_cloud
ros2 topic info /radar_info
```

## Benefits of Two-Topic Architecture

1. **Bandwidth Efficiency:** Static configuration data isn't repeated in every message
2. **Flexible Consumption:** Subscribers can choose to listen to point clouds only or both topics
3. **Better Debugging:** Radar configuration is easily accessible without parsing point cloud messages
4. **Standards Compliance:** Follows ROS2 best practices for sensor data organization
5. **Latched Configuration:** Radar info uses TRANSIENT_LOCAL QoS so late subscribers get configuration

## License

This package is licensed under the MIT License. 


## Example

(ros2_kilted) juhasch@macbook ros2_ws % ros2 topic list
/parameter_events
/radar_info
/radar_point_cloud
/rosout
(ros2_kilted) juhasch@macbook ros2_ws % ros2 topic echo /radar_info --once
header:
  stamp:
    sec: 1759743537
    nanosec: 801574000
  frame_id: radar_link
sensor_model: XWR68xx
firmware_version: ''
serial_number: ''
sensor_status: 0
sensor_info: 'Connected: True, Streaming: True'
is_connected: true
is_streaming: true
carrier_frequency_ghz: 60.0
bandwidth_mhz: 3999.679931640625
frame_period_ms: 125.0
num_tx_antennas: 2
num_rx_antennas: 4
num_adc_samples: 256
adc_sampling_rate_msps: 12500.0
range_resolution: 0.04399999976158142
velocity_resolution: 1.2599999904632568
azimuth_resolution: 0.017000000923871994
elevation_resolution: 0.017000000923871994
max_range: 9.039999961853027
max_velocity: 20.15999984741211
min_range: 0.10000000149011612
min_velocity: 0.10000000149011612
azimuth_fov_min: -1.5700000524520874
azimuth_fov_max: 1.5700000524520874
elevation_fov_min: -0.7900000214576721
elevation_fov_max: 0.7900000214576721
clutter_removal_enabled: false
multi_object_beamforming: false
cfar_threshold: 15.0
range_fft_size: 256
doppler_fft_size: 32
config_file_path: configs/user_profile.cfg
config_file_content: ''
config_timestamp:
  sec: 1759743537
  nanosec: 801592000
---

(ros2_kilted) juhasch@macbook ros2_ws % ros2 topic hz /radar_point_cloud
average rate: 7.980
	min: 0.123s max: 0.130s std dev: 0.00212s window: 7

(ros2_kilted) juhasch@macbook ros2_ws % ros2 topic echo /radar_point_cloud --once
header:
  stamp:
    sec: 1759743627
    nanosec: 430452000
  frame_id: radar_link
frame_number: 1200
num_points: 55
x:
- -0.48538124561309814
- -0.5157175660133362
- -0.5460538864135742
- -0.6025897860527039
...
