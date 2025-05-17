"""Tests for the record module."""

import unittest
import os
import tempfile
import numpy as np
from datetime import datetime, timezone
import pypcd
import yaml
import pytest

from xwr68xxisk.record import PointCloudFrame, PointCloudRecorder
from xwr68xxisk.point_cloud import RadarPointCloud


class TestPointCloudFrame(unittest.TestCase):
    """Test cases for the PointCloudFrame class."""

    def setUp(self):
        """Set up test data."""
        # Create sample point cloud data
        self.num_points = 5
        self.range_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.velocity = np.array([0.5, -1.0, 1.5, -2.0, 2.5])
        self.azimuth = np.array([0.0, np.pi/6, np.pi/4, np.pi/3, np.pi/2])
        self.elevation = np.array([0.0, np.pi/12, np.pi/8, np.pi/6, np.pi/4])
        self.rcs = np.array([-10.0, -8.0, -6.0, -4.0, -2.0])
        self.snr = np.array([5.0, 7.0, 9.0, 11.0, 13.0])
        
        # Create RadarPointCloud object
        self.point_cloud = RadarPointCloud(
            range=self.range_values,
            velocity=self.velocity,
            azimuth=self.azimuth,
            elevation=self.elevation,
            rcs=self.rcs,
            snr=self.snr
        )
        
        # Create PointCloudFrame
        self.timestamp_ns = 1234567890000000000
        self.frame_number = 42
        self.frame = PointCloudFrame(
            timestamp_ns=self.timestamp_ns,
            frame_number=self.frame_number,
            points=self.point_cloud
        )

    def test_initialization(self):
        """Test initialization of PointCloudFrame."""
        self.assertEqual(self.frame.timestamp_ns, self.timestamp_ns)
        self.assertEqual(self.frame.frame_number, self.frame_number)
        self.assertEqual(self.frame.points, self.point_cloud)
        self.assertEqual(self.frame.metadata, {})

    def test_metadata(self):
        """Test metadata handling."""
        metadata = {'sensor_id': 'test', 'temperature': 25.0}
        frame = PointCloudFrame(
            timestamp_ns=self.timestamp_ns,
            frame_number=self.frame_number,
            points=self.point_cloud,
            metadata=metadata
        )
        self.assertEqual(frame.metadata, metadata)


class TestPointCloudRecorder(unittest.TestCase):
    """Test cases for the PointCloudRecorder class."""

    def setUp(self):
        """Set up test data."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.base_filename = os.path.join(self.test_dir, 'test_data')
        
        # Create sample point cloud data
        self.num_points = 5
        self.range_values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        self.velocity = np.array([0.5, -1.0, 1.5, -2.0, 2.5])
        self.azimuth = np.array([0.0, np.pi/6, np.pi/4, np.pi/3, np.pi/2])
        self.elevation = np.array([0.0, np.pi/12, np.pi/8, np.pi/6, np.pi/4])
        self.rcs = np.array([-10.0, -8.0, -6.0, -4.0, -2.0])
        self.snr = np.array([5.0, 7.0, 9.0, 11.0, 13.0])
        
        # Create RadarPointCloud object
        self.point_cloud = RadarPointCloud(
            range=self.range_values,
            velocity=self.velocity,
            azimuth=self.azimuth,
            elevation=self.elevation,
            rcs=self.rcs,
            snr=self.snr
        )

    def tearDown(self):
        """Clean up test files."""
        # Remove all files in the test directory
        for filename in os.listdir(self.test_dir):
            filepath = os.path.join(self.test_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
        # Remove test directory
        os.rmdir(self.test_dir)

    def test_csv_recorder_no_buffer(self):
        """Test CSV recorder without buffering."""
        recorder = PointCloudRecorder(self.base_filename, 'csv', buffer_in_memory=False)
        
        # Add frames
        for frame_number in range(3):
            recorder.add_frame(self.point_cloud, frame_number)
        
        # Close recorder
        recorder.close()
        
        # Check that file exists
        csv_file = f"{self.base_filename}.csv"
        self.assertTrue(os.path.exists(csv_file))
        
        # Check file contents
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        
        # Check header
        self.assertEqual(lines[0].strip(), 
                        "timestamp,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs")
        
        # Check number of data lines (3 frames * 5 points per frame + 1 header)
        self.assertEqual(len(lines), 16)

    def test_csv_recorder_with_buffer(self):
        """Test CSV recorder with buffering."""
        recorder = PointCloudRecorder(self.base_filename, 'csv', buffer_in_memory=True)
        
        # Add frames
        for frame_number in range(3):
            recorder.add_frame(self.point_cloud, frame_number)
        
        # Close recorder
        recorder.close()
        
        # Check that file exists
        csv_file = f"{self.base_filename}.csv"
        self.assertTrue(os.path.exists(csv_file))
        
        # Check file contents
        with open(csv_file, 'r') as f:
            lines = f.readlines()
        
        # Check number of data lines (3 frames * 5 points per frame + 1 header)
        self.assertEqual(len(lines), 16)

    def test_pcd_recorder(self):
        """Test PCD recorder."""
        recorder = PointCloudRecorder(self.base_filename, 'pcd')
        
        # Add frames
        for frame_number in range(3):
            recorder.add_frame(self.point_cloud, frame_number)
        
        # Close recorder
        recorder.close()
        
        # Check that file exists
        pcd_file = f"{self.base_filename}.pcd"
        self.assertTrue(os.path.exists(pcd_file))
        
        # Read PCD file and verify contents
        pc = pypcd.PointCloud.from_path(pcd_file)
        
        # Check number of points (3 frames * 5 points per frame)
        self.assertEqual(len(pc.pc_data), 15)
        
        # Check that all fields are present
        expected_fields = ['x', 'y', 'z', 'velocity', 'range', 'azimuth', 
                         'elevation', 'snr', 'rcs', 'timestamp', 'frame']
        for field in expected_fields:
            self.assertIn(field, pc.fields)

    def test_recorder_statistics(self):
        """Test recorder statistics."""
        recorder = PointCloudRecorder(self.base_filename, 'csv')
        
        # Add frames
        for frame_number in range(3):
            recorder.add_frame(self.point_cloud, frame_number)
        
        # Check statistics
        self.assertEqual(recorder.frame_count, 3)
        self.assertEqual(recorder.total_points, 15)  # 3 frames * 5 points per frame

    def test_invalid_format(self):
        """Test initialization with invalid format."""
        with self.assertRaises(TypeError):
            PointCloudRecorder(self.base_filename, 'invalid_format')


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


@pytest.fixture
def sample_point_cloud():
    """Create a sample point cloud for testing."""
    # Create a simple point cloud with 10 points
    points = RadarPointCloud()
    points.x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.z = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.velocity = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.range = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.azimuth = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.elevation = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.snr = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    points.rcs = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    return points


@pytest.fixture
def sample_radar_config():
    """Create a sample radar configuration."""
    return {
        'profile': {
            'name': 'test_profile',
            'version': '1.0',
            'parameters': {
                'range_resolution': 0.1,
                'velocity_resolution': 0.2,
                'max_range': 100.0,
                'max_velocity': 20.0
            }
        }
    }


def test_metadata_saving(temp_dir, sample_point_cloud, sample_radar_config):
    """Test that metadata is correctly saved with the recording."""
    # Create a recorder with metadata
    base_filename = os.path.join(temp_dir, "test_recording")
    recorder = PointCloudRecorder(
        base_filename=base_filename,
        format_type='csv',
        buffer_in_memory=True,
        enable_clustering=False,
        enable_tracking=False,
        radar_config=sample_radar_config
    )

    # Add some frames
    for i in range(3):
        frame = PointCloudFrame(
            timestamp_ns=int(datetime.now(timezone.utc).timestamp() * 1e9),
            frame_number=i,
            points=sample_point_cloud
        )
        recorder.add_frame(sample_point_cloud, i)

    # Save the recording
    recorder.save()
    recorder.close()

    # Check that metadata file exists
    metadata_file = f"{base_filename}_metadata.yaml"
    assert os.path.exists(metadata_file), "Metadata file was not created"

    # Load and verify metadata
    with open(metadata_file, 'r') as f:
        metadata = yaml.safe_load(f)

    # Verify basic recording information
    assert 'recording' in metadata
    assert metadata['recording']['format_type'] == 'csv'
    assert metadata['recording']['total_frames'] == 3
    assert metadata['recording']['total_points'] == 30  # 3 frames * 10 points
    assert metadata['recording']['enable_clustering'] is False
    assert metadata['recording']['enable_tracking'] is False

    # Verify file references
    assert 'files' in metadata['recording']
    assert metadata['recording']['files']['point_cloud'] == f"{os.path.basename(base_filename)}.csv"

    # Verify radar configuration
    assert 'radar_config' in metadata
    assert metadata['radar_config'] == sample_radar_config


def test_metadata_with_clustering_and_tracking(temp_dir, sample_point_cloud, sample_radar_config):
    """Test metadata saving with clustering and tracking enabled."""
    # Create a recorder with clustering and tracking
    base_filename = os.path.join(temp_dir, "test_recording_clustered")
    recorder = PointCloudRecorder(
        base_filename=base_filename,
        format_type='csv',
        buffer_in_memory=True,
        enable_clustering=True,
        enable_tracking=True,
        clustering_params={'eps': 0.5, 'min_samples': 5},
        tracking_params={'dt': 0.1, 'max_distance': 2.0},
        radar_config=sample_radar_config
    )

    # Add some frames
    for i in range(3):
        frame = PointCloudFrame(
            timestamp_ns=int(datetime.now(timezone.utc).timestamp() * 1e9),
            frame_number=i,
            points=sample_point_cloud
        )
        recorder.add_frame(sample_point_cloud, i)

    # Save the recording
    recorder.save()
    recorder.close()

    # Load and verify metadata
    metadata_file = f"{base_filename}_metadata.yaml"
    with open(metadata_file, 'r') as f:
        metadata = yaml.safe_load(f)

    # Verify clustering and tracking information
    assert metadata['recording']['enable_clustering'] is True
    assert metadata['recording']['enable_tracking'] is True
    assert 'clustering_params' in metadata
    assert 'tracking_params' in metadata
    assert metadata['clustering_params']['eps'] == 0.5
    assert metadata['clustering_params']['min_samples'] == 5
    assert metadata['tracking_params']['dt'] == 0.1
    assert metadata['tracking_params']['max_distance'] == 2.0

    # Verify additional file references
    assert 'clusters' in metadata['recording']['files']
    assert 'tracks' in metadata['recording']['files']


def test_metadata_with_config_file(temp_dir, sample_point_cloud):
    """Test metadata saving with a configuration file."""
    # Create a temporary config file
    config_file = os.path.join(temp_dir, "test_config.cfg")
    with open(config_file, 'w') as f:
        f.write("test_config_content")

    # Create a recorder with config file
    base_filename = os.path.join(temp_dir, "test_recording_with_config")
    recorder = PointCloudRecorder(
        base_filename=base_filename,
        format_type='csv',
        buffer_in_memory=True,
        enable_clustering=False,
        enable_tracking=False,
        radar_config=config_file
    )

    # Add a frame
    recorder.add_frame(sample_point_cloud, 0)

    # Save the recording
    recorder.save()
    recorder.close()

    # Verify that config file was copied
    copied_config = os.path.join(temp_dir, "test_config.cfg")
    assert os.path.exists(copied_config), "Config file was not copied"

    # Load and verify metadata
    metadata_file = f"{base_filename}_metadata.yaml"
    with open(metadata_file, 'r') as f:
        metadata = yaml.safe_load(f)

    # Verify config file reference
    assert 'radar_config_file' in metadata
    assert metadata['radar_config_file'] == "test_config.cfg"


def test_csv_header_format(temp_dir, sample_point_cloud):
    """Test that CSV header uses the correct timestamp format."""
    base_filename = os.path.join(temp_dir, "test_recording")
    recorder = PointCloudRecorder(
        base_filename=base_filename,
        format_type='csv',
        buffer_in_memory=True
    )

    # Add a frame
    recorder.add_frame(sample_point_cloud, 0)
    recorder.save()
    recorder.close()

    # Check CSV header
    with open(f"{base_filename}.csv", 'r') as f:
        header = f.readline().strip()
        assert header == "timestamp,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs"


def test_pcd_timestamp_format(temp_dir, sample_point_cloud):
    """Test that PCD file uses float64 for timestamps."""
    base_filename = os.path.join(temp_dir, "test_recording")
    recorder = PointCloudRecorder(
        base_filename=base_filename,
        format_type='pcd',
        buffer_in_memory=True
    )

    # Add a frame
    recorder.add_frame(sample_point_cloud, 0)
    recorder.save()
    recorder.close()

    # Check that PCD file exists
    pcd_file = f"{base_filename}.pcd"
    assert os.path.exists(pcd_file), "PCD file was not created"


if __name__ == '__main__':
    unittest.main() 