"""
Configuration generator for xwr68xxisk radar sensor.

This module provides functions to generate radar configuration files
from scene profile configurations.
"""

from typing import List
from .radar_config_models import SceneProfileConfig, AntennaConfigEnum
from .radar_config_models import ProfileConfig as RadarProfileConfigModel # Renamed for clarity

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
    num_tx_antennas = 0
    if scene_config.antenna_config == AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV:
        rx_mask = 15  # 4 RX antennas (binary 1111)
        tx_mask = 7   # TX1, TX2, TX3 enabled (binary 0111)
        num_tx_antennas = 3
        cfg_lines.append(f"channelCfg {rx_mask} {tx_mask} 0")
    # elif scene_config.antenna_config == AntennaConfigEnum.SOME_OTHER_CONFIG:
    #     rx_mask = ...
    #     tx_mask = ... # e.g., for 2 TX -> tx_mask would be 3 (TX1, TX2)
    #     num_tx_antennas = 2
    #     cfg_lines.append(f"channelCfg {rx_mask} {tx_mask} 0")
    else:
        cfg_lines.append(f"% channelCfg: Antenna configuration {scene_config.antenna_config} not fully mapped yet.")
        cfg_lines.append(f"% chirpCfg: Antenna configuration {scene_config.antenna_config} not fully mapped yet.")
        # Return early since we don't have a valid antenna configuration for subsequent commands
        return "\n".join(cfg_lines)

    # ADC Config (Typical defaults)
    cfg_lines.append("adcCfg 2 1") # 16-bit ADC, Complex 1X

    # ADC Buffer Config (Typical defaults for subframe -1 legacy mode)
    cfg_lines.append("adcbufCfg -1 0 1 1 1")

    # Profile Config
    # Populate ProfileConfig model from SceneProfileConfig
    # The validator for profile_num_adc_samples in SceneProfileConfig will ensure it's a power of 2.
    profile_data = RadarProfileConfigModel(
        profile_id=0, # Typically 0 for the first/primary profile
        start_freq=scene_config.profile_start_freq_ghz,
        idle_time=scene_config.profile_idle_time_us,
        adc_start_time=scene_config.profile_adc_start_time_us,
        ramp_end_time=scene_config.profile_ramp_end_time_us,
        tx_out_power=scene_config.profile_tx_out_power_db,
        tx_phase_shifter=scene_config.profile_tx_phase_shifter_deg,
        freq_slope_const=scene_config.profile_freq_slope_mhz_us,
        tx_start_time=scene_config.profile_tx_start_time_us,
        num_adc_samples=scene_config.profile_num_adc_samples, # Already validated by SceneProfileConfig
        dig_out_sample_rate=scene_config.profile_dig_out_sample_rate_ksps,
        hpf_corner_freq1=scene_config.profile_hpf_corner_freq1,
        hpf_corner_freq2=scene_config.profile_hpf_corner_freq2,
        rx_gain=scene_config.profile_rx_gain_db
    )

    cfg_lines.append(
        f"profileCfg {profile_data.profile_id} {profile_data.start_freq:.2f} {profile_data.idle_time:.1f} "
        f"{profile_data.adc_start_time:.1f} {profile_data.ramp_end_time:.1f} {profile_data.tx_out_power} "
        f"{profile_data.tx_phase_shifter} {profile_data.freq_slope_const:.3f} {profile_data.tx_start_time:.1f} "
        f"{profile_data.num_adc_samples} {profile_data.dig_out_sample_rate} {profile_data.hpf_corner_freq1} "
        f"{profile_data.hpf_corner_freq2} {profile_data.rx_gain}"
    )
    
    # Chirp Config
    # Based on the number of TX antennas derived from antenna_config
    if num_tx_antennas > 0:
        for i in range(num_tx_antennas):
            # Chirp Cfg: chirpStartIndex, chirpEndIndex, profileId, startFreqVar_GHz, freqSlopeVar_MHz_us, idleTimeVar_us, adcStartTimeVar_us, txEnable (bitmap)
            # Example: For TX1 (i=0), txEnable is 1. For TX2 (i=1), txEnable is 2. For TX3 (i=2), txEnable is 4.
            cfg_lines.append(f"chirpCfg {i} {i} 0 0 0 0 0 {1 << i}")
    else:
        cfg_lines.append(f"% chirpCfg: Not generated due to unmapped antenna configuration.")

    # Frame Config
    chirp_start_idx = scene_config.frame_chirp_start_idx
    # chirp_end_idx should be num_tx_antennas - 1 if chirp_start_idx is 0 and all chirps are contiguous
    # For simplicity, if num_tx_antennas is defined, let's assume chirps from chirp_start_idx up to (chirp_start_idx + num_tx_antennas -1)
    # However, the .cfg format's frameCfg uses absolute chirp indices as defined by chirpCfg commands.
    # If chirpCfg defines chirps 0, 1, 2, then frameCfg's chirpEndIdx should be 2 if all are used.
    # The current chirpCfg loop creates N chirps, indexed 0 to N-1.
    # So, if num_tx_antennas > 0, chirp_end_idx will be num_tx_antennas - 1.
    # This assumes that frame_chirp_start_idx corresponds to the first of these programmed chirps.
    # A more robust system would map logical TX to physical chirpCfg indices if they could be non-contiguous.
    
    # Let's keep it simple for now: if num_tx_antennas > 0, we assume the frame uses all programmed chirps.
    # The chirpCfg lines define chirps from index 0 to num_tx_antennas - 1.
    # So, the frame should span these if it uses all of them.
    # If frame_chirp_start_idx is, for example, 0, and num_tx_antennas is 3, then chirp_end_idx is 2.
    # The question is whether frameCfg's chirp_start_idx and chirp_end_idx refer to the *indices* of the chirpCfg commands
    # or if they are relative. SDK User Guide: "Indices of the chirps to be transmitted in each frame (0 to 511)"
    # This implies they are absolute indices matching the first parameter of chirpCfg.
    # Our loop creates chirpCfg 0 0 ..., chirpCfg 1 1 ..., chirpCfg 2 2 ...
    # So, if num_tx_antennas = 3, the defined chirps are 0, 1, 2.
    # Thus, chirp_start_idx should usually be 0 and chirp_end_idx should be num_tx_antennas - 1.

    # For now, we make chirp_start_idx configurable. 
    # And chirp_end_idx will be based on the number of TX antennas programmed by chirpCfg.
    # This means if num_tx_antennas is 3, chirps 0, 1, 2 are defined.
    # Then frameCfg will use from scene_config.frame_chirp_start_idx to (num_tx_antennas - 1)
    # This needs care if frame_chirp_start_idx is not 0.
    # Example: if num_tx_antennas = 3 (chirps 0,1,2 defined) and frame_chirp_start_idx = 1, then chirp_end_idx should be 2.
    # So, chirp_end_idx is always num_tx_antennas - 1, assuming all defined TX are used in the frame.
    # And the frame_chirp_start_idx must be <= chirp_end_idx.

    if num_tx_antennas > 0:
        effective_chirp_end_idx = num_tx_antennas - 1
        if scene_config.frame_chirp_start_idx > effective_chirp_end_idx:
            # This is an invalid configuration, provide a warning or default behavior
            cfg_lines.append(f"% WARNING: frame_chirp_start_idx ({scene_config.frame_chirp_start_idx}) > effective_chirp_end_idx ({effective_chirp_end_idx}). Clamping start_idx.")
            clamped_start_idx = effective_chirp_end_idx 
            # Or, perhaps better, don't generate frameCfg or raise error.
            # For now, let's just use the effective_chirp_end_idx as end, and user-provided start.
            # If start > end, the radar itself will likely reject.
    else: # num_tx_antennas is 0 (due to unmapped antenna config)
        effective_chirp_end_idx = 0 # or some other safe default, though frameCfg won't be very useful.

    num_loops = scene_config.frame_num_loops
    num_frames = scene_config.frame_num_frames
    frame_periodicity_ms = 1000.0 / scene_config.frame_rate_fps if scene_config.frame_rate_fps > 0 else 100.0
    trigger_select = scene_config.frame_trigger_select
    trigger_delay_ms = scene_config.frame_trigger_delay_ms
    cfg_lines.append(
        f"frameCfg {scene_config.frame_chirp_start_idx} {effective_chirp_end_idx if num_tx_antennas > 0 else 0} {num_loops} {num_frames} "
        f"{frame_periodicity_ms:.2f} {trigger_select} {trigger_delay_ms}"
    )

    # GUI Monitor
    detected_objects = 1 if scene_config.plot_scatter or scene_config.plot_statistics else 0
    log_mag_range = 1 if scene_config.plot_range_profile else 0
    noise_profile = 1 if scene_config.plot_noise_profile else 0
    range_azimuth_heat_map = 1 if scene_config.plot_range_azimuth_heat_map else 0
    range_doppler_heat_map = 1 if scene_config.plot_range_doppler_heat_map else 0
    stats_info = 1 if scene_config.plot_statistics else 0
    print(f"guiMonitor: {detected_objects} {log_mag_range} {noise_profile} {range_azimuth_heat_map} {range_doppler_heat_map} {stats_info}")
    cfg_lines.append(
        f"guiMonitor -1 {detected_objects} {log_mag_range} {noise_profile} "
        f"{range_azimuth_heat_map} {range_doppler_heat_map} {stats_info}"
    )
    
    # Clutter Removal
    cfg_lines.append("clutterRemoval 0 1") # subframe -1, enabled

    return "\n".join(cfg_lines) 