"""
Example script to demonstrate usage of the RadarConfig class
"""

import os
from xwr68xxisk.radar_config import (
    RadarConfig, create_xwr68xx_config,
    DfeDataOutputModeCommand, ChannelConfigCommand, ProfileConfigCommand
)


def print_config_info(config: RadarConfig):
    """Print detailed information about a radar configuration"""
    print(f"Configuration Name: {config.name}")
    print(f"Number of commands: {len(config.commands)}")
    
    # Find and print profile configuration
    profile_cmd = config.get_command("profileCfg")
    if profile_cmd:
        print("\nProfile Configuration:")
        print(f"  Start frequency: {profile_cmd.start_freq} GHz")
        print(f"  Idle time: {profile_cmd.idle_time} µs")
        print(f"  Ramp end time: {profile_cmd.ramp_end_time} µs")
        print(f"  Frequency slope: {profile_cmd.freq_slope_const} MHz/µs")
        print(f"  ADC samples: {profile_cmd.num_adc_samples}")
        print(f"  Sample rate: {profile_cmd.dig_out_sample_rate} ksps")
        print(f"  RX gain: {profile_cmd.rx_gain} dB")
    
    # Find and print channel configuration
    channel_cmd = config.get_command("channelCfg")
    if channel_cmd:
        print("\nChannel Configuration:")
        print(f"  RX antenna mask: {channel_cmd.rx_channel_en:04b}")
        print(f"  TX antenna mask: {channel_cmd.tx_channel_en:04b}")
        print(f"  Cascading: {channel_cmd.cascading}")
    
    # Print frame configuration
    frame_cmd = config.get_command("frameCfg")
    if frame_cmd:
        print("\nFrame Configuration:")
        print(f"  Start chirp index: {frame_cmd.start_idx}")
        print(f"  End chirp index: {frame_cmd.end_idx}")
        print(f"  Number of loops: {frame_cmd.num_loops}")
        print(f"  Number of frames: {frame_cmd.num_frames} (0 = infinite)")
        print(f"  Frame period: {frame_cmd.frame_period_ms} ms")


def example_modify_config():
    """Demonstrate modifying a radar configuration"""
    # Create an XWR68XX configuration
    config = create_xwr68xx_config()
    
    print("Original configuration:")
    print_config_info(config)
    
    # Modify the configuration
    print("\n=== Modifying configuration ===")
    
    # Change frame period
    print("Changing frame period to 150 ms")
    config.update_frame_period(150)
    
    # Change TX antennas
    print("Changing TX antenna mask to use TX1 and TX2 (binary 0011 = 3)")
    config.set_tx_antennas(3)
    
    # Change profile parameters
    print("Updating profile parameters:")
    print("  - Start frequency to 77 GHz")
    print("  - Frequency slope to 60 MHz/µs")
    print("  - ADC samples to 512")
    config.set_profile_parameters(
        start_freq=77.0,
        freq_slope=60.0,
        adc_samples=512
    )
    
    # Enable clutter removal
    print("Enabling clutter removal")
    config.set_clutter_removal(True)
    
    # Print modified configuration
    print("\nModified configuration:")
    print_config_info(config)


def example_create_custom_config():
    """Demonstrate creating a custom radar configuration"""
    # Create a new radar configuration
    config = RadarConfig("custom_config")
    
    # Add common commands (always needed)
    config.add_command(RadarCommand.from_string("sensorStop"))
    config.add_command(RadarCommand.from_string("flushCfg"))
    
    # Add data output mode
    dfe_cmd = DfeDataOutputModeCommand([1])  # Frame-based chirps
    config.add_command(dfe_cmd)
    
    # Add channel config (use all 4 RX antennas, TX1 and TX3)
    # RX mask: 1111 (all 4 RX), TX mask: 0101 (TX1 and TX3)
    channel_cmd = ChannelConfigCommand([15, 5, 0])
    config.add_command(channel_cmd)
    
    # Add ADC config
    config.add_command(RadarCommand.from_string("adcCfg 2 1"))
    
    # Add ADC buffer config 
    config.add_command(RadarCommand.from_string("adcbufCfg -1 0 1 1 1"))
    
    # Add profile config
    profile_cmd = ProfileConfigCommand([
        0,           # profile ID
        77.0,        # start frequency in GHz
        100.0,       # idle time in μs
        6.0,         # ADC start time in μs
        60.0,        # ramp end time in μs
        0,           # TX output power
        0,           # TX phase shifter
        80.0,        # freq slope in MHz/μs
        1,           # TX start time
        512,         # ADC samples
        6000,        # ADC sample rate in ksps
        0,           # HPF corner freq 1
        0,           # HPF corner freq 2
        160          # RX gain in dB
    ])
    config.add_command(profile_cmd)
    
    # Add chirp config
    config.add_command(RadarCommand.from_string("chirpCfg 0 0 0 0 0 0 0 1"))
    
    # Add frame config (0 start, 0 end, 32 loops, infinite frames, 100ms period)
    config.add_command(RadarCommand.from_string("frameCfg 0 0 32 0 100 1 0"))
    
    # Print the custom configuration information
    print("\nCustom Configuration:")
    print_config_info(config)
    
    # Print the string representation
    print("\nConfiguration String:")
    print(config.to_string())
    
    return config


def example_file_operations():
    """Demonstrate file I/O operations with radar configurations"""
    # Create a custom configuration
    custom_config = example_create_custom_config()
    
    # Save to file
    output_file = "custom_radar_config.cfg"
    print(f"\n=== Saving config to {output_file} ===")
    custom_config.to_file(output_file)
    print(f"Configuration saved to {output_file}")
    
    # Load from file
    print(f"\n=== Loading config from {output_file} ===")
    loaded_config = RadarConfig.from_file(output_file)
    print(f"Loaded configuration: {loaded_config.name}")
    print(f"Number of commands: {len(loaded_config.commands)}")
    
    # Verify it's the same
    print("\nVerifying loaded configuration matches original:")
    orig_str = custom_config.to_string()
    loaded_str = loaded_config.to_string()
    if orig_str == loaded_str:
        print("Success! Configurations match.")
    else:
        print("Error: Configurations don't match.")
    
    # Clean up the file
    os.remove(output_file)
    print(f"Removed {output_file}")


def example_clone_config():
    """Demonstrate cloning and modifying a configuration"""
    # Get original config
    orig_config = create_xwr68xx_config()
    
    # Clone the configuration
    print("\n=== Cloning and Modifying Configuration ===")
    long_range_config = orig_config.clone()
    long_range_config.name = "xwr68xx_long_range"
    
    # Modify the clone for long-range configuration
    # Increase chirp loop count
    frame_cmd = long_range_config.get_command("frameCfg")
    if frame_cmd:
        frame_cmd.num_loops = 64  # Increase from original 16
        print(f"Modified number of loops: {frame_cmd.num_loops}")
    
    # Increase ADC samples
    profile_cmd = long_range_config.get_command("profileCfg")
    if profile_cmd:
        profile_cmd.num_adc_samples = 512  # Increase from original 256
        print(f"Modified ADC samples: {profile_cmd.num_adc_samples}")
    
    # Decrease frame rate for more integration time
    long_range_config.update_frame_period(200)  # Increase from 100ms
    print(f"Modified frame period: {long_range_config.get_command('frameCfg').frame_period_ms} ms")
    
    # Print configurations to compare
    print("\nOriginal Configuration:")
    print_config_info(orig_config)
    
    print("\nLong Range Configuration:")
    print_config_info(long_range_config)


if __name__ == "__main__":
    # Import RadarCommand for custom config example
    from xwr68xxisk.radar_config import RadarCommand
    
    print("=== Radar Configuration Examples ===\n")
    
    # Demonstrate modifying a configuration
    example_modify_config()
    
    # Demonstrate file I/O operations
    example_file_operations()
    
    # Demonstrate cloning and specialized configuration
    example_clone_config() 