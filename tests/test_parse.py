import pytest
import numpy as np
from xwr68xxisk.parse import RadarData, MAGIC_NUMBER

def test_invalid_magic_number():
    """Test that invalid magic number raises ValueError."""
    # Create dummy data with wrong magic number
    data = bytearray(100)  # Create dummy data
    with pytest.raises(ValueError):
        RadarData(data)

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