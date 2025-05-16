"""
Configuration generator for xwr68xxisk radar sensor.

This module provides functions to generate radar configuration files
from scene profile configurations.
"""

from typing import List
from .radar_config_models import SceneProfileConfig, AntennaConfigEnum

def generate_cfg_from_scene_profile(scene_config: SceneProfileConfig) -> str:
    """
    Generate a radar configuration string (.cfg format) from a SceneProfileConfig object.

    Parameters
    ----------
    scene_config : SceneProfileConfig
        The scene profile configuration to convert to .cfg format

    Returns
    -------
    str
        The generated configuration string in .cfg format

    Notes
    -----
    This function generates a complete .cfg file content that can be sent to the radar.
    It includes all necessary configuration commands like channel configuration,
    profile configuration, chirp configuration, and frame configuration.
    """
    cfg_lines = ["% Profile generated from GUI"]

    # DFE Data Output Mode (Always 1 for this application typically)
    cfg_lines.append("dfeDataOutputMode 1")

    # Channel Config - Basic mapping from antenna_config
    if scene_config.antenna_config == AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV:
        rx_mask = 15  # 4 RX antennas (binary 1111)
        tx_mask = 7   # Assuming TX1, TX2, TX3 (binary 0111) - specific to hardware
        cfg_lines.append(f"channelCfg {rx_mask} {tx_mask} 0")
    else:
        cfg_lines.append("% channelCfg: Antenna configuration not fully mapped yet")
        cfg_lines.append("% chirpCfg: Antenna configuration not fully mapped yet")
        # Return early since we don't have a valid antenna configuration
        return "\n".join(cfg_lines)

    # ADC Config (Typical defaults)
    cfg_lines.append("adcCfg 2 1") # 16-bit ADC, Complex 1X

    # ADC Buffer Config (Typical defaults for subframe -1 legacy mode)
    cfg_lines.append("adcbufCfg -1 0 1 1 1")

    # Profile Config
    profile_id = 0
    start_freq_ghz = 60.25 # Typical for IWR6843
    idle_time_us = 7.0
    adc_start_time_us = 6.0
    ramp_end_time_us = 60.0
    tx_out_power_db = 0 # Max power
    tx_phase_shifter_deg = 0
    freq_slope_mhz_us = 20.0 # Placeholder, needs calculation based on range_res & max_range
    tx_start_time_us = 1.0
    num_adc_samples = 256 # Placeholder
    dig_out_sample_rate_ksps = 5000 # Placeholder
    hpf_corner_freq1 = 0 # 0: 175 KHz, 1: 235 KHz, 2: 350 KHz, 3: 700 KHz
    hpf_corner_freq2 = 0 # 0: 350 KHz, 1: 700 KHz, 2: 1.4 MHz, 3: 2.8 MHz
    rx_gain_db = 30 # Typical

    cfg_lines.append(
        f"profileCfg {profile_id} {start_freq_ghz:.2f} {idle_time_us:.1f} "
        f"{adc_start_time_us:.1f} {ramp_end_time_us:.1f} {tx_out_power_db} "
        f"{tx_phase_shifter_deg} {freq_slope_mhz_us:.3f} {tx_start_time_us:.1f} "
        f"{num_adc_samples} {dig_out_sample_rate_ksps} {hpf_corner_freq1} "
        f"{hpf_corner_freq2} {rx_gain_db}"
    )
    
    # Chirp Config
    if scene_config.antenna_config == AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV:
        cfg_lines.append("chirpCfg 0 0 0 0 0 0 0 1") # TX1
        cfg_lines.append("chirpCfg 1 1 0 0 0 0 0 2") # TX2
        cfg_lines.append("chirpCfg 2 2 0 0 0 0 0 4") # TX3

    # Frame Config
    chirp_start_idx = 0
    chirp_end_idx = 2 # Assuming 3 chirps (0, 1, 2) for 3TX example
    num_loops = 64 # Number of doppler bins
    num_frames = 0 # Infinite frames
    frame_periodicity_ms = 1000.0 / scene_config.frame_rate_fps if scene_config.frame_rate_fps > 0 else 100.0
    trigger_select = 1 # Software trigger
    trigger_delay_ms = 0
    cfg_lines.append(
        f"frameCfg {chirp_start_idx} {chirp_end_idx} {num_loops} {num_frames} "
        f"{frame_periodicity_ms:.2f} {trigger_select} {trigger_delay_ms}"
    )

    # GUI Monitor
    detected_objects = 1 if scene_config.plot_scatter or scene_config.plot_statistics else 0
    log_mag_range = 1 if scene_config.plot_range_profile else 0
    noise_profile = 1 if scene_config.plot_noise_profile else 0
    range_azimuth_heat_map = 1 if scene_config.plot_range_azimuth_heat_map else 0
    range_doppler_heat_map = 1 if scene_config.plot_range_doppler_heat_map else 0
    stats_info = 1 if scene_config.plot_statistics else 0
    cfg_lines.append(
        f"guiMonitor {detected_objects} {log_mag_range} {noise_profile} "
        f"{range_azimuth_heat_map} {range_doppler_heat_map} {stats_info}"
    )
    
    # Clutter Removal
    cfg_lines.append("clutterRemoval 0 1") # subframe -1, enabled

    return "\n".join(cfg_lines) 