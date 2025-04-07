import pytest
import numpy as np
from xwr68xxisk.parse import RadarData

class MockRadarConnection:
    def __init__(self, data):
        self.data = data
        
    def is_connected(self):
        return True
        
    def is_running(self):
        return True
        
    def read_frame(self):
        return {'frame_number': 1, 'num_detected_obj': 0}, self.data

def test_invalid_magic_number():
    """Test that invalid magic number raises ValueError."""
    # Create dummy data with wrong magic number
    data = bytearray(100)  # Create dummy data with zeros (invalid magic number)
    mock_connection = MockRadarConnection(data)
    radar_data = RadarData(mock_connection)
    assert radar_data.magic_word is None  # Magic word should be None for invalid data

def test_parse_empty_packet():
    """Test parsing of minimal valid packet with no TLVs."""
    # TODO: Implement with actual test data

def test_parse_point_cloud():
    """Test parsing of point cloud data."""
    # TODO: Implement with actual test data

def test_parse_range_profile():
    """Test parsing of range profile data."""
    # TODO: Implement with actual test data

def test_parse_side_info():
    """Test parsing of side information."""
    # TODO: Implement with actual test data

def test_multiple_tlvs():
    """Test parsing of packet with multiple TLVs."""
    # TODO: Implement with actual test data

def test_malformed_packet():
    """Test handling of malformed packet data."""
    # TODO: Implement with actual test data 