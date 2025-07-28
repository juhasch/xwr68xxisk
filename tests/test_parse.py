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
        return {'frame_number': 1, 'num_tlvs': 2}, self.data

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
    # Create mock data with both range profile and noise profile TLVs
    # Range profile (TLV type 2)
    range_tlv_type = 2
    range_tlv_length = 512
    range_samples = range_tlv_length // 2
    range_data = np.random.randint(100, 2000, range_samples, dtype=np.uint16)
    
    # Noise profile (TLV type 3)
    noise_tlv_type = 3
    noise_tlv_length = 512
    noise_samples = noise_tlv_length // 2
    noise_data = np.random.randint(50, 500, noise_samples, dtype=np.uint16)
    
    # Create packet with both TLVs
    packet = bytearray()
    
    # Add range profile TLV
    packet.extend(range_tlv_type.to_bytes(4, byteorder='little'))
    packet.extend(range_tlv_length.to_bytes(4, byteorder='little'))
    packet.extend(range_data.tobytes())
    
    # Add noise profile TLV
    packet.extend(noise_tlv_type.to_bytes(4, byteorder='little'))
    packet.extend(noise_tlv_length.to_bytes(4, byteorder='little'))
    packet.extend(noise_data.tobytes())
    
    # Create mock radar connection
    mock_connection = MockRadarConnection(packet)
    
    # Create radar data object
    radar_data = RadarData(mock_connection)
    
    # Verify that both range profile and noise profile were parsed correctly
    assert radar_data.adc is not None
    assert len(radar_data.adc) == range_samples
    assert radar_data.adc.dtype == np.uint16
    
    assert radar_data.noise_profile is not None
    assert len(radar_data.noise_profile) == noise_samples
    assert radar_data.noise_profile.dtype == np.uint16
    
    # Test get_noise_profile method
    noise_db, range_axis = radar_data.get_noise_profile()
    assert len(noise_db) == noise_samples
    assert len(range_axis) == noise_samples
    assert noise_db.dtype == np.float32 or noise_db.dtype == np.float64
    assert range_axis.dtype == np.float32 or range_axis.dtype == np.float64 