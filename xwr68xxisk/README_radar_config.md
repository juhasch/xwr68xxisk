# Radar Configuration Module

This module provides an object-oriented approach to manage radar configurations for Texas Instruments mmWave radar sensors. It replaces hardcoded string configurations with a structured, programmatic interface.

## Features

- Converts radar configuration strings to structured objects
- Provides type-safe access to configuration parameters
- Enables modifying configurations through a well-defined API
- Supports saving configurations to files and loading from files
- Maintains backward compatibility with string-based configurations
- Easy cloning and customization of configurations

## Quick Start

```python
from radar_config import RadarConfig, create_xwr68xx_config

# Load a predefined configuration
config = create_xwr68xx_config()

# Modify parameters
config.set_tx_antennas(3)  # Use TX1 and TX2 antennas
config.update_frame_period(150)  # Set frame period to 150ms
config.set_profile_parameters(
    start_freq=77.0,  # GHz
    freq_slope=60.0,  # MHz/μs
    adc_samples=512
)

# Save to a file
config.to_file("my_custom_config.cfg")

# Create a specialized version
long_range_config = config.clone()
long_range_config.name = "long_range"
frame_cmd = long_range_config.get_command("frameCfg")
frame_cmd.num_loops = 64  # Increase from original 16
```

## Main Classes

### RadarCommand

Base class representing a single configuration command with parameters.

```python
# Create a command manually
cmd = RadarCommand("profileCfg", [0, 77, 100, 6, 60, 0, 0, 80, 1, 512, 6000, 0, 0, 160])

# Parse from string
cmd = RadarCommand.from_string("profileCfg 0 77 100 6 60 0 0 80 1 512 6000 0 0 160")
```

### Specialized Command Classes

The module provides specialized classes for common radar commands, with typed properties:

- `DfeDataOutputModeCommand`
- `ChannelConfigCommand`
- `AdcConfigCommand`
- `AdcBufConfigCommand`
- `ProfileConfigCommand`
- `ChirpConfigCommand`
- `FrameConfigCommand`
- `GuiMonitorCommand`
- `CfarConfigCommand`
- `MultiObjBeamFormingCommand`
- `ClutterRemovalCommand`
- And more...

These provide type-safe access to command parameters:

```python
profile_cmd = config.get_command("profileCfg")
print(f"Start frequency: {profile_cmd.start_freq} GHz")
print(f"Number of ADC samples: {profile_cmd.num_adc_samples}")
```

### RadarConfig

Main class that manages a complete radar configuration.

```python
# Create from configuration string
config = RadarConfig.from_string(config_str, "my_config")

# Load from file
config = RadarConfig.from_file("radar_config.cfg")

# Create a custom configuration
config = RadarConfig("custom_config")
config.add_command(RadarCommand.from_string("sensorStop"))
config.add_command(RadarCommand.from_string("flushCfg"))
config.add_command(DfeDataOutputModeCommand([1]))
# ...
```

## Using with Existing Code

The module maintains backward compatibility with code that expects string configurations:

```python
# Get configuration as a string
config_str = config.to_string()

# Later, convert back to object if needed
config = RadarConfig.from_string(config_str)
```

## Helper Methods

The `RadarConfig` class provides helper methods for common operations:

- `update_frame_period(period_ms)`: Update the frame period
- `set_tx_antennas(tx_antenna_mask)`: Set which TX antennas to use
- `set_rx_antennas(rx_antenna_mask)`: Set which RX antennas to use
- `set_profile_parameters(...)`: Update profile parameters
- `set_clutter_removal(enabled)`: Enable/disable clutter removal
- `clone()`: Create a copy of the configuration

## Examples

See the `radar_config_example.py` file for complete usage examples. 