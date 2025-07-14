# ROS2 message for mmWave radar point cloud data
# This message contains detected points from a mmWave radar sensor
# Static radar configuration is published separately on RadarInfo topic

# Standard header with timestamp and frame_id
std_msgs/Header header

# Frame information
uint32 frame_number        # Frame sequence number from radar
uint32 num_points          # Number of detected points in this frame

# Point cloud data arrays (all arrays must have same length = num_points)
# Position data (Cartesian coordinates)
float32[] x                # X coordinates in meters (forward from radar)
float32[] y                # Y coordinates in meters (right from radar)  
float32[] z                # Z coordinates in meters (up from radar)

# Spherical coordinates (native radar measurements)
float32[] range            # Distance from radar in meters
float32[] azimuth          # Horizontal angle in radians (-π to π)
float32[] elevation        # Vertical angle in radians (-π/2 to π/2)

# Velocity data
float32[] velocity         # Radial velocity in m/s (positive = moving away)

# Signal quality metrics
float32[] snr              # Signal-to-noise ratio in dB
float32[] rcs              # Radar cross-section in dBsm (decibels relative to square meter)

# Additional radar-specific data (optional, may be empty)
float32[] noise            # Noise level in dB (if available)
uint16[] doppler_bin       # Doppler bin index (if available)
float32[] intensity        # Signal intensity in arbitrary units (if available) 