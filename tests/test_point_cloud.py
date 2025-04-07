"""
Tests for the RadarPointCloud class.

This module contains pytest tests for the RadarPointCloud class to ensure
all functionality works correctly.
"""

import pytest
import numpy as np
from xwr68xxisk.point_cloud import RadarPointCloud


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    num_points = 5
    range_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    velocity = np.array([0.5, -1.0, 1.5, -2.0, 2.5])
    azimuth = np.array([0.0, np.pi/6, np.pi/4, np.pi/3, np.pi/2])
    elevation = np.array([0.0, np.pi/12, np.pi/8, np.pi/6, np.pi/4])
    rcs = np.array([-10.0, -8.0, -6.0, -4.0, -2.0])
    snr = np.array([5.0, 7.0, 9.0, 11.0, 13.0])
    metadata = {"frame_number": 42, "timestamp": 12345.6789}
    
    return {
        'num_points': num_points,
        'range': range_values,
        'velocity': velocity,
        'azimuth': azimuth,
        'elevation': elevation,
        'rcs': rcs,
        'snr': snr,
        'metadata': metadata
    }


@pytest.fixture
def point_cloud(sample_data):
    """Create a point cloud object with the sample data."""
    return RadarPointCloud(
        range=sample_data['range'],
        velocity=sample_data['velocity'],
        azimuth=sample_data['azimuth'],
        elevation=sample_data['elevation'],
        rcs=sample_data['rcs'],
        snr=sample_data['snr'],
        metadata=sample_data['metadata']
    )


@pytest.fixture
def cartesian_coords():
    """Create Cartesian coordinates for testing."""
    return {
        'x': np.array([0.0, 1.0, 2.0, 3.0, 4.0]),
        'y': np.array([0.0, 2.0, 3.0, 4.0, 5.0]),
        'z': np.array([0.0, 0.5, 1.0, 1.5, 2.0])
    }


def test_initialization(point_cloud, sample_data):
    """Test initialization of RadarPointCloud."""
    # Test with provided data
    assert point_cloud.num_points == sample_data['num_points']
    np.testing.assert_array_equal(point_cloud.range, sample_data['range'])
    np.testing.assert_array_equal(point_cloud.velocity, sample_data['velocity'])
    np.testing.assert_array_equal(point_cloud.azimuth, sample_data['azimuth'])
    np.testing.assert_array_equal(point_cloud.elevation, sample_data['elevation'])
    np.testing.assert_array_equal(point_cloud.rcs, sample_data['rcs'])
    np.testing.assert_array_equal(point_cloud.snr, sample_data['snr'])
    assert point_cloud.metadata == sample_data['metadata']
    
    # Test with default values (empty arrays)
    empty_point_cloud = RadarPointCloud()
    assert empty_point_cloud.num_points == 0
    assert len(empty_point_cloud.range) == 0
    assert len(empty_point_cloud.velocity) == 0
    assert len(empty_point_cloud.azimuth) == 0
    assert len(empty_point_cloud.elevation) == 0
    assert len(empty_point_cloud.rcs) == 0
    assert len(empty_point_cloud.snr) == 0
    assert empty_point_cloud.metadata == {}


def test_validate_arrays(point_cloud):
    """Test array validation."""
    # Test with valid arrays (same length)
    point_cloud._validate_arrays()  # Should not raise any exception
    
    # Test with invalid arrays (different lengths)
    with pytest.raises(ValueError):
        RadarPointCloud(
            range=np.array([1.0, 2.0, 3.0]),
            velocity=np.array([0.5, -1.0])  # Different length
        )


def test_num_points(point_cloud, sample_data):
    """Test num_points property."""
    assert point_cloud.num_points == sample_data['num_points']
    
    # Test with empty point cloud
    empty_point_cloud = RadarPointCloud()
    assert empty_point_cloud.num_points == 0


def test_to_cartesian(point_cloud, sample_data):
    """Test conversion from spherical to Cartesian coordinates."""
    x, y, z = point_cloud.to_cartesian()
    
    # Calculate expected values manually for verification
    expected_x = sample_data['range'] * np.cos(sample_data['elevation']) * np.sin(sample_data['azimuth'])
    expected_y = sample_data['range'] * np.cos(sample_data['elevation']) * np.cos(sample_data['azimuth'])
    expected_z = sample_data['range'] * np.sin(sample_data['elevation'])
    
    # Check that the calculated values match the expected values
    np.testing.assert_array_almost_equal(x, expected_x)
    np.testing.assert_array_almost_equal(y, expected_y)
    np.testing.assert_array_almost_equal(z, expected_z)
    
    # Test with empty point cloud
    empty_point_cloud = RadarPointCloud()
    x_empty, y_empty, z_empty = empty_point_cloud.to_cartesian()
    assert len(x_empty) == 0
    assert len(y_empty) == 0
    assert len(z_empty) == 0


def test_get_cartesian_points(point_cloud, sample_data):
    """Test getting point cloud as Nx3 array of Cartesian coordinates."""
    points = point_cloud.get_cartesian_points()
    
    # Check shape
    assert points.shape == (sample_data['num_points'], 3)
    
    # Calculate expected values
    x, y, z = point_cloud.to_cartesian()
    expected_points = np.column_stack((x, y, z))
    
    # Check that the calculated values match the expected values
    np.testing.assert_array_almost_equal(points, expected_points)
    
    # Test with empty point cloud
    empty_point_cloud = RadarPointCloud()
    empty_points = empty_point_cloud.get_cartesian_points()
    assert empty_points.shape == (0, 3)


def test_from_cartesian(cartesian_coords, sample_data):
    """Test creation of RadarPointCloud from Cartesian coordinates."""
    # Create a point cloud from Cartesian coordinates
    point_cloud_from_cartesian = RadarPointCloud.from_cartesian(
        x=cartesian_coords['x'],
        y=cartesian_coords['y'],
        z=cartesian_coords['z'],
        velocity=sample_data['velocity'],
        rcs=sample_data['rcs'],
        snr=sample_data['snr']
    )
    
    # Calculate expected values
    expected_range = np.sqrt(cartesian_coords['x']**2 + cartesian_coords['y']**2 + cartesian_coords['z']**2)
    expected_azimuth = np.arctan2(cartesian_coords['x'], cartesian_coords['y'])
    # Handle zero range and ensure z/range is within [-1, 1] for arcsin
    expected_elevation = np.zeros_like(expected_range)
    mask = expected_range > 0
    if np.any(mask):
        z_over_r = np.clip(cartesian_coords['z'][mask] / expected_range[mask], -1, 1)
        expected_elevation[mask] = np.arcsin(z_over_r)
    
    # Check that the calculated values match the expected values
    assert point_cloud_from_cartesian.num_points == len(cartesian_coords['x'])
    np.testing.assert_array_almost_equal(point_cloud_from_cartesian.range, expected_range)
    np.testing.assert_array_almost_equal(point_cloud_from_cartesian.azimuth, expected_azimuth)
    np.testing.assert_array_almost_equal(point_cloud_from_cartesian.elevation, expected_elevation)
    np.testing.assert_array_equal(point_cloud_from_cartesian.velocity, sample_data['velocity'])
    np.testing.assert_array_equal(point_cloud_from_cartesian.rcs, sample_data['rcs'])
    np.testing.assert_array_equal(point_cloud_from_cartesian.snr, sample_data['snr'])
    
    # Test with default values for velocity, rcs, and snr
    point_cloud_defaults = RadarPointCloud.from_cartesian(
        x=cartesian_coords['x'],
        y=cartesian_coords['y'],
        z=cartesian_coords['z']
    )
    
    # Check that default values are zeros
    np.testing.assert_array_equal(point_cloud_defaults.velocity, np.zeros_like(cartesian_coords['x']))
    np.testing.assert_array_equal(point_cloud_defaults.rcs, np.zeros_like(cartesian_coords['x']))
    np.testing.assert_array_equal(point_cloud_defaults.snr, np.zeros_like(cartesian_coords['x']))
    
    # Test with invalid input (different array lengths)
    with pytest.raises(ValueError):
        RadarPointCloud.from_cartesian(
            x=cartesian_coords['x'],
            y=cartesian_coords['y'][:-1],  # Different length
            z=cartesian_coords['z']
        )


def test_from_radar_frame():
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
    assert point_cloud_from_frame.num_points == 5
    np.testing.assert_array_equal(point_cloud_from_frame.range, point_cloud_data[:, 0])
    np.testing.assert_array_equal(point_cloud_from_frame.azimuth, point_cloud_data[:, 1])
    np.testing.assert_array_equal(point_cloud_from_frame.elevation, point_cloud_data[:, 2])
    np.testing.assert_array_equal(point_cloud_from_frame.velocity, point_cloud_data[:, 3])
    np.testing.assert_array_equal(point_cloud_from_frame.snr, point_cloud_data[:, 4])
    np.testing.assert_array_equal(point_cloud_from_frame.rcs, np.zeros_like(point_cloud_data[:, 0]))
    assert point_cloud_from_frame.metadata == frame_data
    
    # Test with empty point cloud data
    empty_point_cloud_data = np.array([])
    empty_point_cloud_from_frame = RadarPointCloud.from_radar_frame(frame_data, empty_point_cloud_data)
    assert empty_point_cloud_from_frame.num_points == 0


def test_roundtrip_conversion(point_cloud, sample_data):
    """Test roundtrip conversion from spherical to Cartesian and back."""
    # Convert to Cartesian
    x, y, z = point_cloud.to_cartesian()
    
    # Convert back to spherical
    point_cloud_roundtrip = RadarPointCloud.from_cartesian(
        x=x,
        y=y,
        z=z,
        velocity=sample_data['velocity'],
        rcs=sample_data['rcs'],
        snr=sample_data['snr']
    )
    
    # Check that the values match the original values
    np.testing.assert_array_almost_equal(point_cloud_roundtrip.range, sample_data['range'])
    np.testing.assert_array_almost_equal(point_cloud_roundtrip.azimuth, sample_data['azimuth'])
    np.testing.assert_array_almost_equal(point_cloud_roundtrip.elevation, sample_data['elevation'])
    np.testing.assert_array_equal(point_cloud_roundtrip.velocity, sample_data['velocity'])
    np.testing.assert_array_equal(point_cloud_roundtrip.rcs, sample_data['rcs'])
    np.testing.assert_array_equal(point_cloud_roundtrip.snr, sample_data['snr']) 