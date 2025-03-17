"""Tests for the record module."""

import unittest
import os
import tempfile
import numpy as np
from datetime import datetime
import pypcd

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
        # Remove test files
        for ext in ['.csv', '.pcd']:
            filepath = f"{self.base_filename}{ext}"
            if os.path.exists(filepath):
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
                        "timestamp_ns,frame,x,y,z,velocity,range,azimuth,elevation,snr,rcs")
        
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
                         'elevation', 'snr', 'rcs', 'timestamp_ns', 'frame']
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


if __name__ == '__main__':
    unittest.main() 