# Installation

## Prerequisites

Before installing the XWR68XX ISK Radar Tools, ensure you have:

1. Python 3.8 or higher installed
2. pip package manager
3. XWR68XX ISK radar sensor hardware
4. USB connection to the radar sensor

## Installation Steps

1. Clone the repository or download the source code.

2. Install the package using pip:
   ```bash
   pip install .
   ```

## Verifying Installation

To verify that the installation was successful, run:

```bash
xwr68xxisk --help
```

You should see the help message with available commands and options:

```bash
usage: xwr68xxisk [-h] [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--serial-number SERIAL_NUMBER] {gui,record} ...

XWR68XX ISK Radar Tools

positional arguments:
  {gui,record}          Available commands
    gui                 Start the radar GUI
    record             Record radar data to CSV file

options:
  -h, --help           show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                       Set the logging level (default: INFO)
  --serial-number SERIAL_NUMBER
                       Radar serial number in hex format "1234ABCD"
```

## Troubleshooting

If you encounter any issues during installation:

1. Make sure all prerequisites are met
2. Check that the USB ports are properly connected
3. Verify that you have the correct permissions to access the USB ports
4. Ensure the dip switches on the board are set correctly (OFF-OFF-ON-ON-OFF-OFF) 