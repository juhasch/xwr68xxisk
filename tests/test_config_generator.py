"""
Tests for the configuration generator module.

This module contains tests for the radar configuration generation functionality.
"""

import pytest
from xwr68xxisk.config_generator import generate_cfg_from_scene_profile
from xwr68xxisk.radar_config_models import RadarConfig, AntennaConfigEnum
from enum import Enum

def test_basic_config_generation():
    """Test basic configuration generation with default values."""
    # Create a basic scene config
    config = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        frame_rate_fps=10.0
    )
    
    # Generate config
    cfg_str = generate_cfg_from_scene_profile(config)
    
    # Basic validation
    assert "% Profile generated from GUI" in cfg_str
    assert "dfeDataOutputMode 1" in cfg_str
    assert "channelCfg 15 7 0" in cfg_str  # 4RX, 3TX configuration
    assert "adcCfg 2 1" in cfg_str
    assert "adcbufCfg -1 0 1 1 1" in cfg_str
    assert "clutterRemoval 0 1" in cfg_str

def test_frame_config_generation():
    """Test frame configuration generation with different frame rates."""
    # Test with 10 FPS
    config_10fps = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        frame_rate_fps=10.0
    )
    cfg_str_10fps = generate_cfg_from_scene_profile(config_10fps)
    assert "frameCfg 0 2 64 0 100.00 1 0" in cfg_str_10fps
    
    # Test with 20 FPS
    config_20fps = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        frame_rate_fps=20.0
    )
    cfg_str_20fps = generate_cfg_from_scene_profile(config_20fps)
    assert "frameCfg 0 2 64 0 50.00 1 0" in cfg_str_20fps

def test_gui_monitor_config():
    """Test GUI monitor configuration based on plot settings."""
    # Test with all plots enabled
    config_all_plots = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        plot_scatter=True,
        plot_statistics=True,
        plot_range_profile=True,
        plot_noise_profile=True,
        plot_range_azimuth_heat_map=True,
        plot_range_doppler_heat_map=True
    )
    cfg_str_all = generate_cfg_from_scene_profile(config_all_plots)
    assert "guiMonitor 1 1 1 1 1 1" in cfg_str_all
    
    # Test with no plots enabled
    config_no_plots = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        plot_scatter=False,
        plot_statistics=False,
        plot_range_profile=False,
        plot_noise_profile=False,
        plot_range_azimuth_heat_map=False,
        plot_range_doppler_heat_map=False
    )
    cfg_str_none = generate_cfg_from_scene_profile(config_no_plots)
    assert "guiMonitor 0 0 0 0 0 0" in cfg_str_none

def test_chirp_config():
    """Test chirp configuration generation."""
    config = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV
    )
    cfg_str = generate_cfg_from_scene_profile(config)
    
    # Check for all three TX configurations
    assert "chirpCfg 0 0 0 0 0 0 0 1" in cfg_str  # TX1
    assert "chirpCfg 1 1 0 0 0 0 0 2" in cfg_str  # TX2
    assert "chirpCfg 2 2 0 0 0 0 0 4" in cfg_str  # TX3

def test_unsupported_antenna_config():
    """Test handling of unsupported antenna configurations."""
    # Create config with unsupported antenna config by directly setting the value
    # to bypass the model validation
    config = RadarConfig()
    config.antenna_config = "Unsupported Config"  # Directly set to bypass validation
    
    cfg_str = generate_cfg_from_scene_profile(config)
    
    # Should include placeholder comment
    assert "% channelCfg: Antenna configuration not fully mapped yet" in cfg_str
    assert "% chirpCfg: Antenna configuration not fully mapped yet" in cfg_str

def test_profile_config_format():
    """Test the format of the profile configuration line."""
    from xwr68xxisk.radar_config_models import (
        DfeDataOutputModeConfig, ChannelConfig, AdcConfig, AdcBufConfig, ProfileConfig,
        ModeType, AdcOutputFormat, AdcBits
    )
    config = RadarConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        dfe_data_output_mode=DfeDataOutputModeConfig(mode_type=ModeType.FRAME_BASED_CHIRPS),
        channel_cfg=ChannelConfig(rx_channel_en=15, tx_channel_en=5, cascading=0),
        adc_cfg=AdcConfig(num_adc_bits=AdcBits.BITS_12, adc_output_fmt=AdcOutputFormat.COMPLEX_UNFILTERED),
        adc_buf_cfg=AdcBufConfig(subframe_idx=-1, adc_output_fmt=0, sample_swap=1, chan_interleave=1, chirp_threshold=1),
        profile_cfg=ProfileConfig(profile_id=0, start_freq=60.0, idle_time=7.0, adc_start_time=3.0, ramp_end_time=24.0, freq_slope_const=166.0, tx_start_time=1.0, num_adc_samples=256, dig_out_sample_rate=12500, hpf_corner_freq1=0, hpf_corner_freq2=0, rx_gain=158.0)
    )
    cfg_str = generate_cfg_from_scene_profile(config)
    
    # Find the profileCfg line
    profile_lines = [line for line in cfg_str.split('\n') if line.startswith('profileCfg')]
    assert len(profile_lines) == 1
    
    # Check the format and number of parameters
    profile_parts = profile_lines[0].split()
    assert len(profile_parts) == 15  # profileCfg + 14 parameters
    assert profile_parts[0] == 'profileCfg'
    
    # Check some specific values
    assert float(profile_parts[2]) == 60.0   # start_freq_ghz
    assert float(profile_parts[3]) == 7.0    # idle_time_us
    assert float(profile_parts[4]) == 3.0    # adc_start_time_us
    assert float(profile_parts[5]) == 24.0   # ramp_end_time_us 