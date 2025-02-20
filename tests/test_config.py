import pytest
from pathlib import Path
from pydantic import ValidationError
from xwr68xxisk.config import (
    RadarConfigParser, ProfileConfig, FrameConfig, 
    RadarConfig, parse_config_file
)

@pytest.fixture
def sample_config_path(tmp_path):
    config_content = """
% Test config file
sensorStop
flushCfg
profileCfg 0 60 567 7 57.14 0 0 70 1 256 5209 0 0 158
frameCfg 0 1 16 0 100 1 0
"""
    config_file = tmp_path / "test_config.cfg"
    config_file.write_text(config_content)
    return config_file

def test_profile_config():
    profile = ProfileConfig(
        start_freq=60,
        idle_time=7,
        ramp_end_time=57.14,
        freq_slope=70,
        num_adc_samples=256,
        dig_out_sample_rate=5209
    )
    assert profile.num_adc_samples == 256
    
    # Test power of 2 rounding
    profile = ProfileConfig(
        start_freq=60,
        idle_time=7,
        ramp_end_time=57.14,
        freq_slope=70,
        num_adc_samples=250,  # Should round up to 256
        dig_out_sample_rate=5209
    )
    assert profile.num_adc_samples == 256

def test_frame_config():
    frame = FrameConfig(
        chirp_start_idx=0,
        chirp_end_idx=1,
        num_loops=16,
        frame_periodicity=100
    )
    assert frame.num_chirps_per_frame == 32

def test_parse_config_file(sample_config_path):
    config = RadarConfigParser.parse_config_file(sample_config_path)
    assert isinstance(config, RadarConfig)
    
    # Test that all values are positive
    assert all(v > 0 for v in config.dict().values())
    
    # Test specific values
    assert config.num_range_bins == 256

def test_legacy_parse_config_file(sample_config_path):
    params = parse_config_file(sample_config_path)
    assert isinstance(params, dict)
    assert params["num_range_bins"] == 256

def test_missing_config_file():
    with pytest.raises(FileNotFoundError):
        RadarConfigParser.parse_config_file("nonexistent_file.cfg")

def test_invalid_config_file(tmp_path):
    invalid_config = tmp_path / "invalid.cfg"
    invalid_config.write_text("invalid content")
    
    with pytest.raises(ValueError):
        RadarConfigParser.parse_config_file(invalid_config) 