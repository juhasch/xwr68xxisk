# API Reference

This section provides detailed information about the Python API of the XWR68XX ISK Radar Tools.

## Command Line Interface

### Main Entry Points

The package provides two main commands:
- `gui`: Launches the radar visualization GUI
- `record`: Records radar data to CSV files

### Common Options

Both commands support the following options:

- `--log-level`: Set logging verbosity
  - Type: string
  - Choices: DEBUG, INFO, WARNING, ERROR, CRITICAL
  - Default: INFO

- `--serial-number`: Specify radar serial number
  - Type: string
  - Format: Hexadecimal (e.g., "1234ABCD")
  - Optional: Yes

## Python API

The package can also be used as a Python library:

```python
from xwr68xxisk import RadarSensor

# Initialize radar sensor
radar = RadarSensor()

# Connect to radar
radar.connect()

# Start radar operation
radar.start()

# Get radar data
data = radar.get_frame()

# Stop radar
radar.stop()

# Disconnect
radar.disconnect()
```

### RadarSensor Class

The main class for interacting with the radar sensor.

#### Methods

- `connect()`: Establish connection with the radar
  - Returns: bool - True if successful

- `disconnect()`: Close connection with the radar
  - Returns: None

- `start()`: Start radar operation
  - Returns: bool - True if successful

- `stop()`: Stop radar operation
  - Returns: None

- `get_frame()`: Get the latest radar frame
  - Returns: numpy.ndarray - Array of point cloud data

#### Properties

- `serial_number`: Get the radar's serial number
  - Type: str
  - Read-only

- `is_connected`: Check if radar is connected
  - Type: bool
  - Read-only

- `is_running`: Check if radar is operating
  - Type: bool
  - Read-only

## Data Format

### CSV File Structure

The recorded CSV files contain the following columns:

1. `timestamp`: Unix timestamp in seconds
2. `frame`: Frame number
3. `x`: X coordinate in meters
4. `y`: Y coordinate in meters
5. `z`: Z coordinate in meters
6. `velocity`: Radial velocity in m/s
7. `intensity`: Signal intensity (arbitrary units)

### Point Cloud Data Structure

The point cloud data returned by `get_frame()` is a NumPy array with shape (N, 5) where:
- N: Number of points in the frame
- Columns: [x, y, z, velocity, intensity] 