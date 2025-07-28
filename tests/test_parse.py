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
        return {'frame_number': 1, 'num_tlvs': 1}, self.data

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

def test_parse_noise_profile():
    """Test parsing of noise profile data."""
    # Create mock data with TLV type 3 (noise profile)
    # TLV header: type=3, length=512 (256 uint16 values)
    tlv_type = 3
    tlv_length = 512
    num_samples = tlv_length // 2  # 256 uint16 values
    
    # Create mock noise profile data (uint16 values)
    noise_data = np.random.randint(0, 1000, num_samples, dtype=np.uint16)
    
    # Create packet with TLV header and data
    packet = bytearray()
    packet.extend(tlv_type.to_bytes(4, byteorder='little'))  # TLV type
    packet.extend(tlv_length.to_bytes(4, byteorder='little'))  # TLV length
    packet.extend(noise_data.tobytes())  # TLV data
    
    # Create mock radar connection
    mock_connection = MockRadarConnection(packet)
    
    # Create radar data object
    radar_data = RadarData(mock_connection)
    
    # Verify that noise profile was parsed correctly
    assert radar_data.noise_profile is not None
    assert len(radar_data.noise_profile) == num_samples
    assert radar_data.noise_profile.dtype == np.uint16
    
    # Test get_noise_profile method
    noise_db, range_axis = radar_data.get_noise_profile()
    assert len(noise_db) == num_samples
    assert len(range_axis) == num_samples
    assert noise_db.dtype == np.float32 or noise_db.dtype == np.float64
    assert range_axis.dtype == np.float32 or range_axis.dtype == np.float64 