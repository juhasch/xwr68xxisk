"""Tests for the IMU BNO086 interface."""

import unittest
from unittest.mock import Mock, patch
import time
from xwr68xxisk.imu import IMU


class TestIMU(unittest.TestCase):
    """Test cases for the IMU class."""

    def setUp(self):
        """Set up test fixtures."""
        # Example message from documentation
        self.test_message = bytes.fromhex('AAAA DE 0100 92FF 2508 8DFE ECFF D103 000000 E7')
        self.expected_values = {
            'index': 0xDE,
            'yaw': 0.01,
            'pitch': -1.10,
            'roll': 20.85,
            'x_acceleration': -371,
            'y_acceleration': -20,
            'z_acceleration': 977,
            'motion_intent': 0,
            'motion_request': 0
        }

    @patch('serial.Serial')
    def test_decode_data(self, mock_serial):
        """Test decoding of a known message."""
        # Create IMU instance with mocked serial
        mock_serial.return_value.read.return_value = self.test_message
        imu = IMU('/dev/ttyUSB0')
        
        # Test decoding
        result = imu.decode_data(self.test_message)
        
        # Check all values match expected
        self.assertEqual(result['index'], self.expected_values['index'])
        self.assertAlmostEqual(result['yaw'], self.expected_values['yaw'], places=2)
        self.assertAlmostEqual(result['pitch'], self.expected_values['pitch'], places=2)
        self.assertAlmostEqual(result['roll'], self.expected_values['roll'], places=2)
        self.assertEqual(result['x_acceleration'], self.expected_values['x_acceleration'])
        self.assertEqual(result['y_acceleration'], self.expected_values['y_acceleration'])
        self.assertEqual(result['z_acceleration'], self.expected_values['z_acceleration'])
        self.assertEqual(result['motion_intent'], self.expected_values['motion_intent'])
        self.assertEqual(result['motion_request'], self.expected_values['motion_request'])

    @patch('serial.Serial')
    def test_invalid_header(self, mock_serial):
        """Test handling of invalid header."""
        # Create message with invalid header
        invalid_header = bytes.fromhex('BBBB' + 'DE 0100 92FF 2508 8DFE ECFF D103 000000 E7')
        mock_serial.return_value.read.return_value = invalid_header
        imu = IMU('/dev/ttyUSB0')
        
        # Should return None for invalid header
        result = imu.decode_data(invalid_header)
        self.assertIsNone(result)

    @patch('serial.Serial')
    def test_invalid_checksum(self, mock_serial):
        """Test handling of invalid checksum."""
        # Create message with invalid checksum
        invalid_checksum = bytes.fromhex('AAAA DE 0100 92FF 2508 8DFE ECFF D103 000000 F7')
        mock_serial.return_value.read.return_value = invalid_checksum
        imu = IMU('/dev/ttyUSB0')
        
        # Should return None for invalid checksum
        result = imu.decode_data(invalid_checksum)
        self.assertIsNone(result)

    @patch('serial.Serial')
    def test_incomplete_message(self, mock_serial):
        """Test handling of incomplete message."""
        # Create incomplete message
        incomplete = bytes.fromhex('AAAA DE 0100')
        mock_serial.return_value.read.return_value = incomplete
        imu = IMU('/dev/ttyUSB0')
        
        # Should return None for incomplete message
        result = imu.decode_data(incomplete)
        self.assertIsNone(result)

    @patch('serial.Serial')
    def test_iterator_interface(self, mock_serial):
        """Test the iterator interface."""
        mock_serial.return_value.read.return_value = self.test_message
        imu = IMU('/dev/ttyUSB0')
        
        # Wait for first reading
        time.sleep(0.02)  # Wait for at least one reading at 100Hz
        
        # Get reading through iterator
        reading = next(imu)
        
        # Verify reading matches expected values
        self.assertAlmostEqual(reading['yaw'], self.expected_values['yaw'], places=2)
        self.assertAlmostEqual(reading['pitch'], self.expected_values['pitch'], places=2)
        self.assertAlmostEqual(reading['roll'], self.expected_values['roll'], places=2)


if __name__ == '__main__':
    unittest.main() 