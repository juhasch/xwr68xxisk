"""
Radar Point Cloud module for TI mmWave radar sensors.

This module provides a class to store and process radar point cloud data from TI mmWave
radar sensors, including methods to convert between spherical and Cartesian coordinates.
"""

import numpy as np
from typing import Optional, Dict, Any, Tuple


class RadarPointCloud:
    """
    Class to store and process radar point cloud data.
    
    This class stores the important attributes of radar point cloud data:
    - range: distance from the radar to the detected point (in meters)
    - velocity: radial velocity of the detected point (in m/s)
    - azimuth: horizontal angle of the detected point (in radians)
    - elevation: vertical angle of the detected point (in radians)
    - rcs: radar cross-section, a measure of reflectivity (in dBsm)
    - snr: signal-to-noise ratio (in dB)
    
    It also provides methods to convert between spherical and Cartesian coordinates.
    """
    
    def __init__(self, 
                 range: Optional[np.ndarray] = None,
                 velocity: Optional[np.ndarray] = None,
                 azimuth: Optional[np.ndarray] = None,
                 elevation: Optional[np.ndarray] = None,
                 rcs: Optional[np.ndarray] = None,
                 snr: Optional[np.ndarray] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a RadarPointCloud object.
        
        Args:
            range: Array of distances from the radar to the detected points (in meters)
            velocity: Array of radial velocities of the detected points (in m/s)
            azimuth: Array of horizontal angles of the detected points (in radians)
            elevation: Array of vertical angles of the detected points (in radians)
            rcs: Array of radar cross-sections, a measure of reflectivity (in dBsm)
            snr: Array of signal-to-noise ratios (in dB)
            metadata: Dictionary containing additional metadata about the point cloud
        """
        self.range = range if range is not None else np.array([])
        self.velocity = velocity if velocity is not None else np.array([])
        self.azimuth = azimuth if azimuth is not None else np.array([])
        self.elevation = elevation if elevation is not None else np.array([])
        self.rcs = rcs if rcs is not None else np.array([])
        self.snr = snr if snr is not None else np.array([])
        self.metadata = metadata if metadata is not None else {}
        
        # Validate that all arrays have the same length
        self._validate_arrays()
        
    def _validate_arrays(self) -> None:
        """
        Validate that all point cloud arrays have the same length.
        
        Raises:
            ValueError: If arrays have inconsistent lengths
        """
        arrays = [self.range, self.velocity, self.azimuth, self.elevation, self.rcs, self.snr]
        lengths = [len(arr) for arr in arrays if len(arr) > 0]
        
        if not lengths:
            return  # All arrays are empty
            
        if not all(length == lengths[0] for length in lengths):
            raise ValueError("All point cloud arrays must have the same length")
    
    @property
    def num_points(self) -> int:
        """
        Get the number of points in the point cloud.
        
        Returns:
            int: Number of points
        """
        return len(self.range)
    
    def to_cartesian(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Convert spherical coordinates (range, azimuth, elevation) to Cartesian coordinates (x, y, z).
        
        The coordinate system follows the convention:
        - x-axis: points in front of the radar (forward)
        - y-axis: points to the right of the radar
        - z-axis: points upward
        
        Returns:
            Tuple containing:
                x: Array of x-coordinates (in meters)
                y: Array of y-coordinates (in meters)
                z: Array of z-coordinates (in meters)
        """
        if self.num_points == 0:
            return np.array([]), np.array([]), np.array([])
            
        # Convert spherical to Cartesian coordinates
        x = self.range * np.cos(self.elevation) * np.sin(self.azimuth)
        y = self.range * np.cos(self.elevation) * np.cos(self.azimuth)
        z = self.range * np.sin(self.elevation)
        
        return x, y, z
    
    def get_cartesian_points(self) -> np.ndarray:
        """
        Get the point cloud as a Nx3 array of Cartesian coordinates.
        
        Returns:
            np.ndarray: Nx3 array where each row is [x, y, z] in meters
        """
        if self.num_points == 0:
            return np.zeros((0, 3))
            
        x, y, z = self.to_cartesian()
        return np.column_stack((x, y, z))
    
    @classmethod
    def from_cartesian(cls, 
                      x: np.ndarray, 
                      y: np.ndarray, 
                      z: np.ndarray, 
                      velocity: Optional[np.ndarray] = None,
                      rcs: Optional[np.ndarray] = None,
                      snr: Optional[np.ndarray] = None) -> 'RadarPointCloud':
        """
        Create a RadarPointCloud from Cartesian coordinates.
        
        Args:
            x: Array of x-coordinates (in meters)
            y: Array of y-coordinates (in meters)
            z: Array of z-coordinates (in meters)
            velocity: Array of radial velocities (in m/s)
            rcs: Array of radar cross-sections (in dBsm)
            snr: Array of signal-to-noise ratios (in dB)
            
        Returns:
            RadarPointCloud: New instance with converted coordinates
        """
        # Ensure all input arrays have the same length
        if not (len(x) == len(y) == len(z)):
            raise ValueError("x, y, and z arrays must have the same length")
            
        # Calculate range
        range_values = np.sqrt(x**2 + y**2 + z**2)
        
        # Calculate azimuth (horizontal angle)
        azimuth = np.arctan2(x, y)
        
        # Calculate elevation (vertical angle)
        # Handle zero range and ensure z/range is within [-1, 1] for arcsin
        mask = range_values > 0
        elevation = np.zeros_like(range_values)
        if np.any(mask):
            z_over_r = np.clip(z[mask] / range_values[mask], -1, 1)
            elevation[mask] = np.arcsin(z_over_r)
        
        # If velocity, rcs, or snr are not provided, create arrays of zeros
        if velocity is None:
            velocity = np.zeros_like(x)
        if rcs is None:
            rcs = np.zeros_like(x)
        if snr is None:
            snr = np.zeros_like(x)
            
        return cls(range=range_values, velocity=velocity, azimuth=azimuth, 
                  elevation=elevation, rcs=rcs, snr=snr)
    
    @classmethod
    def from_radar_frame(cls, frame_data: Dict[str, Any], point_cloud_data: np.ndarray) -> 'RadarPointCloud':
        """
        Create a RadarPointCloud from radar frame data.
        
        This method is intended to be used with the data returned by the radar.read_frame() method.
        
        Args:
            frame_data: Dictionary containing frame metadata
            point_cloud_data: Array containing point cloud data
            
        Returns:
            RadarPointCloud: New instance with data from the radar frame
        """
        # This method would need to be customized based on the specific format
        # of the data returned by the radar.read_frame() method
        
        # Example implementation (to be adjusted based on actual data format):
        if point_cloud_data.size == 0:
            return cls()
            
        # Assuming point_cloud_data is structured with columns for each attribute
        # The actual implementation would depend on the specific data format
        range_values = point_cloud_data[:, 0]
        azimuth = point_cloud_data[:, 1]
        elevation = point_cloud_data[:, 2]
        velocity = point_cloud_data[:, 3]
        snr = point_cloud_data[:, 4]
        
        # RCS might not be directly available and might need to be calculated
        rcs = np.zeros_like(range_values)
        
        return cls(range=range_values, velocity=velocity, azimuth=azimuth,
                  elevation=elevation, rcs=rcs, snr=snr, metadata=frame_data)

    def to_cartesian_2d(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert spherical coordinates (range, azimuth) to 2D Cartesian coordinates (x, y).
        
        The coordinate system follows the convention:
        - x-axis: points in front of the radar (forward)
        - y-axis: points to the right of the radar
        
        Returns:
            Tuple containing:
                x: Array of x-coordinates (in meters)
                y: Array of y-coordinates (in meters)
        """
        if self.num_points == 0:
            return np.array([]), np.array([])
            
        # Convert spherical to Cartesian coordinates
        x = self.range * np.sin(self.azimuth)
        y = self.range * np.cos(self.azimuth)
        
        return x, y

    @classmethod
    def from_cartesian_2d(cls, x: np.ndarray, y: np.ndarray) -> 'RadarPointCloud':
        """
        Create a RadarPointCloud from 2D Cartesian coordinates.
        
        Args:
            x: Array of x-coordinates (in meters)
            y: Array of y-coordinates (in meters)
            
        Returns:
            RadarPointCloud: New instance with converted coordinates
        """
        # Ensure all input arrays have the same length
        if not (len(x) == len(y)):
            raise ValueError("x and y arrays must have the same length")
            
        # Calculate range
        range_values = np.sqrt(x**2 + y**2)
        
        # Calculate azimuth (horizontal angle)
        azimuth = np.arctan2(x, y)
        
        # If velocity, rcs, or snr are not provided, create arrays of zeros
        velocity = np.zeros_like(x)
        rcs = np.zeros_like(x)
        snr = np.zeros_like(x)
        
        return cls(range=range_values, velocity=velocity, azimuth=azimuth, 
                  elevation=np.zeros_like(range_values), rcs=rcs, snr=snr) 