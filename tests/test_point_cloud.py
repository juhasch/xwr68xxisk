"""
Tests for the RadarPointCloud class.

This module contains unit tests for the RadarPointCloud class to ensure
all functionality works correctly.
"""

import unittest
import numpy as np
from xwr68xxisk.point_cloud import RadarPointCloud


class TestRadarPointCloud(unittest.TestCase):
    """Test cases for the RadarPointCloud class."""

    def setUp(self):
        """Set up test data."""
        # Create sample data for testing
        self.num_points = 5
        self.range_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.velocity = np.array([0.5, -1.0, 1.5, -2.0, 2.5])
        self.azimuth = np.array([0.0, np.pi/6, np.pi/4, np.pi/3, np.pi/2])
        self.elevation = np.array([0.0, np.pi/12, np.pi/8, np.pi/6, np.pi/4])
        self.rcs = np.array([-10.0, -8.0, -6.0, -4.0, -2.0])
        self.snr = np.array([5.0, 7.0, 9.0, 11.0, 13.0])
        self.metadata = {"frame_number": 42, "timestamp": 12345.6789}
        
        # Create a point cloud object with the sample data
        self.point_cloud = RadarPointCloud(
            range=self.range_values,
            velocity=self.velocity,
            azimuth=self.azimuth,
            elevation=self.elevation,
            rcs=self.rcs,
            snr=self.snr,
            metadata=self.metadata
        )
        
        # Create Cartesian coordinates for testing
        self.x = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        self.y = np.array([0.0, 2.0, 3.0, 4.0, 5.0])
        self.z = np.array([0.0, 0.5, 1.0, 1.5, 2.0])

    def test_initialization(self):
        """Test initialization of RadarPointCloud."""
        # Test with provided data
        self.assertEqual(self.point_cloud.num_points, self.num_points)
        np.testing.assert_array_equal(self.point_cloud.range, self.range_values)
        np.testing.assert_array_equal(self.point_cloud.velocity, self.velocity)
        np.testing.assert_array_equal(self.point_cloud.azimuth, self.azimuth)
        np.testing.assert_array_equal(self.point_cloud.elevation, self.elevation)
        np.testing.assert_array_equal(self.point_cloud.rcs, self.rcs)
        np.testing.assert_array_equal(self.point_cloud.snr, self.snr)
        self.assertEqual(self.point_cloud.metadata, self.metadata)
        
        # Test with default values (empty arrays)
        empty_point_cloud = RadarPointCloud()
        self.assertEqual(empty_point_cloud.num_points, 0)
        self.assertEqual(len(empty_point_cloud.range), 0)
        self.assertEqual(len(empty_point_cloud.velocity), 0)
        self.assertEqual(len(empty_point_cloud.azimuth), 0)
        self.assertEqual(len(empty_point_cloud.elevation), 0)
        self.assertEqual(len(empty_point_cloud.rcs), 0)
        self.assertEqual(len(empty_point_cloud.snr), 0)
        self.assertEqual(empty_point_cloud.metadata, {})

    def test_validate_arrays(self):
        """Test array validation."""
        # Test with valid arrays (same length)
        try:
            self.point_cloud._validate_arrays()
        except ValueError:
            self.fail("_validate_arrays() raised ValueError unexpectedly!")
            
        # Test with invalid arrays (different lengths)
        with self.assertRaises(ValueError):
            invalid_point_cloud = RadarPointCloud(
                range=np.array([1.0, 2.0, 3.0]),
                velocity=np.array([0.5, -1.0])  # Different length
            )

    def test_num_points(self):
        """Test num_points property."""
        self.assertEqual(self.point_cloud.num_points, self.num_points)
        
        # Test with empty point cloud
        empty_point_cloud = RadarPointCloud()
        self.assertEqual(empty_point_cloud.num_points, 0)

    def test_to_cartesian(self):
        """Test conversion from spherical to Cartesian coordinates."""
        x, y, z = self.point_cloud.to_cartesian()
        
        # Calculate expected values manually for verification
        expected_x = self.range_values * np.cos(self.elevation) * np.sin(self.azimuth)
        expected_y = self.range_values * np.cos(self.elevation) * np.cos(self.azimuth)
        expected_z = self.range_values * np.sin(self.elevation)
        
        # Check that the calculated values match the expected values
        np.testing.assert_array_almost_equal(x, expected_x)
        np.testing.assert_array_almost_equal(y, expected_y)
        np.testing.assert_array_almost_equal(z, expected_z)
        
        # Test with empty point cloud
        empty_point_cloud = RadarPointCloud()
        x_empty, y_empty, z_empty = empty_point_cloud.to_cartesian()
        self.assertEqual(len(x_empty), 0)
        self.assertEqual(len(y_empty), 0)
        self.assertEqual(len(z_empty), 0)

    def test_get_cartesian_points(self):
        """Test getting point cloud as Nx3 array of Cartesian coordinates."""
        points = self.point_cloud.get_cartesian_points()
        
        # Check shape
        self.assertEqual(points.shape, (self.num_points, 3))
        
        # Calculate expected values
        x, y, z = self.point_cloud.to_cartesian()
        expected_points = np.column_stack((x, y, z))
        
        # Check that the calculated values match the expected values
        np.testing.assert_array_almost_equal(points, expected_points)
        
        # Test with empty point cloud
        empty_point_cloud = RadarPointCloud()
        empty_points = empty_point_cloud.get_cartesian_points()
        self.assertEqual(empty_points.shape, (0, 3))

    def test_from_cartesian(self):
        """Test creation of RadarPointCloud from Cartesian coordinates."""
        # Create a point cloud from Cartesian coordinates
        point_cloud_from_cartesian = RadarPointCloud.from_cartesian(
            x=self.x,
            y=self.y,
            z=self.z,
            velocity=self.velocity,
            rcs=self.rcs,
            snr=self.snr
        )
        
        # Calculate expected values
        expected_range = np.sqrt(self.x**2 + self.y**2 + self.z**2)
        expected_azimuth = np.arctan2(self.x, self.y)
        expected_elevation = np.arcsin(self.z / expected_range)
        
        # Check that the calculated values match the expected values
        self.assertEqual(point_cloud_from_cartesian.num_points, len(self.x))
        np.testing.assert_array_almost_equal(point_cloud_from_cartesian.range, expected_range)
        np.testing.assert_array_almost_equal(point_cloud_from_cartesian.azimuth, expected_azimuth)
        np.testing.assert_array_almost_equal(point_cloud_from_cartesian.elevation, expected_elevation)
        np.testing.assert_array_equal(point_cloud_from_cartesian.velocity, self.velocity)
        np.testing.assert_array_equal(point_cloud_from_cartesian.rcs, self.rcs)
        np.testing.assert_array_equal(point_cloud_from_cartesian.snr, self.snr)
        
        # Test with default values for velocity, rcs, and snr
        point_cloud_defaults = RadarPointCloud.from_cartesian(
            x=self.x,
            y=self.y,
            z=self.z
        )
        
        # Check that default values are zeros
        np.testing.assert_array_equal(point_cloud_defaults.velocity, np.zeros_like(self.x))
        np.testing.assert_array_equal(point_cloud_defaults.rcs, np.zeros_like(self.x))
        np.testing.assert_array_equal(point_cloud_defaults.snr, np.zeros_like(self.x))
        
        # Test with invalid input (different array lengths)
        with self.assertRaises(ValueError):
            RadarPointCloud.from_cartesian(
                x=self.x,
                y=self.y[:-1],  # Different length
                z=self.z
            )

    def test_from_radar_frame(self):
        """Test creation of RadarPointCloud from radar frame data."""
        # Create sample frame data
        frame_data = {"frame_number": 42, "timestamp": 12345.6789}
        
        # Create sample point cloud data (5 points with 5 attributes each)
        point_cloud_data = np.array([
            [1.0, 0.0, 0.0, 0.5, 5.0],
            [2.0, np.pi/6, np.pi/12, -1.0, 7.0],
            [3.0, np.pi/4, np.pi/8, 1.5, 9.0],
            [4.0, np.pi/3, np.pi/6, -2.0, 11.0],
            [5.0, np.pi/2, np.pi/4, 2.5, 13.0]
        ])
        
        # Create a point cloud from radar frame data
        point_cloud_from_frame = RadarPointCloud.from_radar_frame(frame_data, point_cloud_data)
        
        # Check that the values match the expected values
        self.assertEqual(point_cloud_from_frame.num_points, 5)
        np.testing.assert_array_equal(point_cloud_from_frame.range, point_cloud_data[:, 0])
        np.testing.assert_array_equal(point_cloud_from_frame.azimuth, point_cloud_data[:, 1])
        np.testing.assert_array_equal(point_cloud_from_frame.elevation, point_cloud_data[:, 2])
        np.testing.assert_array_equal(point_cloud_from_frame.velocity, point_cloud_data[:, 3])
        np.testing.assert_array_equal(point_cloud_from_frame.snr, point_cloud_data[:, 4])
        np.testing.assert_array_equal(point_cloud_from_frame.rcs, np.zeros_like(point_cloud_data[:, 0]))
        self.assertEqual(point_cloud_from_frame.metadata, frame_data)
        
        # Test with empty point cloud data
        empty_point_cloud_data = np.array([])
        empty_point_cloud_from_frame = RadarPointCloud.from_radar_frame(frame_data, empty_point_cloud_data)
        self.assertEqual(empty_point_cloud_from_frame.num_points, 0)

    def test_roundtrip_conversion(self):
        """Test roundtrip conversion from spherical to Cartesian and back."""
        # Convert to Cartesian
        x, y, z = self.point_cloud.to_cartesian()
        
        # Convert back to spherical
        point_cloud_roundtrip = RadarPointCloud.from_cartesian(
            x=x,
            y=y,
            z=z,
            velocity=self.velocity,
            rcs=self.rcs,
            snr=self.snr
        )
        
        # Check that the values match the original values
        np.testing.assert_array_almost_equal(point_cloud_roundtrip.range, self.range_values)
        np.testing.assert_array_almost_equal(point_cloud_roundtrip.azimuth, self.azimuth)
        np.testing.assert_array_almost_equal(point_cloud_roundtrip.elevation, self.elevation)
        np.testing.assert_array_equal(point_cloud_roundtrip.velocity, self.velocity)
        np.testing.assert_array_equal(point_cloud_roundtrip.rcs, self.rcs)
        np.testing.assert_array_equal(point_cloud_roundtrip.snr, self.snr)


if __name__ == "__main__":
    unittest.main() 