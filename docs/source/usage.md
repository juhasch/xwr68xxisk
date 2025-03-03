# Usage Guide

The XWR68XX ISK Radar Tools provide two main functionalities:
1. Recording radar data to CSV files
2. Displaying radar data in real-time using a GUI

## Command Line Interface

### Recording Data

To record radar data to a CSV file:

```bash
xwr68xxisk record
```

This will:
1. Automatically detect the radar sensor's USB ports
2. Configure the radar
3. Start recording data to a CSV file in the `recordings` directory

Example output:
```bash
2025-02-20 09:49:47 - INFO - Found CLI port: /dev/ttyUSB0
2025-02-20 09:49:47 - INFO - Found Data port: /dev/ttyUSB1
2025-02-20 09:49:47 - INFO - Serial number: 00F48B0C
2025-02-20 09:49:50 - INFO - Radar configured and started
Recording data to recordings/radar_data_20250220_094947.csv
Press Ctrl+C to stop recording
Frame: 12, Points: 15
```

To stop recording, press Ctrl+C.

### Using the GUI

To start the radar visualization GUI:

```bash
xwr68xxisk gui
```

The GUI provides:
- Real-time point cloud visualization
- 100ms update rate
- Simple controls for connecting and starting the radar

## GUI Usage Guide

1. Launch the GUI using the command above
2. Click "Connect" to establish connection with the radar
3. Click "Start" to begin radar operation and visualization
4. The point cloud will update in real-time

## Advanced Options

### Setting Log Level

You can adjust the logging verbosity:

```bash
xwr68xxisk --log-level DEBUG gui
```

Available log levels:
- DEBUG
- INFO (default)
- WARNING
- ERROR
- CRITICAL

### Specifying Serial Number

If you have multiple radar sensors, you can specify which one to use:

```bash
xwr68xxisk --serial-number 1234ABCD gui
```

The serial number is a unique identifier in hex format that can be found on the USB interface of the sensor. 