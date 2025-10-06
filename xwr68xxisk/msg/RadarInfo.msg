# ROS2 message for mmWave radar sensor information and configuration
# This message contains static radar configuration and sensor capabilities
# Published infrequently (once per session or when configuration changes)

# Standard header with timestamp and frame_id
std_msgs/Header header

# Radar sensor identification
string sensor_model         # Radar sensor model (e.g., "XWR68xx", "AWR2544")
string firmware_version     # Firmware version
string serial_number        # Sensor serial number (if available)

# Current sensor status
uint8 sensor_status          # Overall sensor status (0=OK, 1=WARNING, 2=ERROR)
string sensor_info           # Additional sensor information/warnings
bool is_connected            # Whether radar is connected
bool is_streaming            # Whether radar is actively streaming data

# Radar configuration parameters
float32 carrier_frequency_ghz    # Carrier frequency in GHz
float32 bandwidth_mhz           # Bandwidth in MHz
float32 frame_period_ms         # Frame period in milliseconds
uint32 num_tx_antennas          # Number of TX antennas
uint32 num_rx_antennas          # Number of RX antennas
uint32 num_adc_samples          # Number of ADC samples
float32 adc_sampling_rate_msps  # ADC sampling rate in Msps

# Measurement capabilities and resolutions
float32 range_resolution        # Range resolution in meters
float32 velocity_resolution     # Velocity resolution in m/s
float32 azimuth_resolution      # Azimuth resolution in radians
float32 elevation_resolution    # Elevation resolution in radians

# Maximum measurement ranges
float32 max_range               # Maximum unambiguous range in meters
float32 max_velocity            # Maximum unambiguous velocity in m/s
float32 min_range               # Minimum detectable range in meters
float32 min_velocity            # Minimum detectable velocity in m/s

# Field of view
float32 azimuth_fov_min         # Minimum azimuth angle in radians
float32 azimuth_fov_max         # Maximum azimuth angle in radians
float32 elevation_fov_min       # Minimum elevation angle in radians
float32 elevation_fov_max       # Maximum elevation angle in radians

# Signal processing configuration
bool clutter_removal_enabled    # Whether static clutter removal is enabled
bool multi_object_beamforming   # Whether multi-object beamforming is enabled
float32 cfar_threshold          # CFAR detection threshold
uint32 range_fft_size           # Range FFT size
uint32 doppler_fft_size         # Doppler FFT size

# Configuration source information
string config_file_path         # Path to configuration file used
string config_file_content      # Raw configuration file content (optional)
builtin_interfaces/Time config_timestamp  # When configuration was loaded 