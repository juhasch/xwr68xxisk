"""
Configuration generator for xwr68xxisk radar sensor.

This module provides functions to generate radar configuration files
from scene profile configurations.
"""

from typing import List
from .radar_config_models import RadarConfig
from .radar_config_models import ProfileConfig as RadarProfileConfigModel # Renamed for clarity
from .radar_config_models import AntennaConfigEnum

def generate_cfg_from_scene_profile(scene_config: RadarConfig) -> str:
    """
    Generate a radar configuration string (.cfg format) from a SceneProfileConfig object.
    Always outputs a full, valid configuration for first-time sensor start, with all required commands in correct order.
    """
    cfg_lines = ["% Profile generated from GUI"]

    # --- Required preamble ---
    cfg_lines.append("sensorStop")
    cfg_lines.append("flushCfg")

    # --- Core configuration ---
    cfg_lines.append("dfeDataOutputMode 1")
    # Channel config (use antenna_config or default)
    rx_mask = 15
    tx_mask = 5  # Use TX1 and TX3 only (binary 101), matching working profile
    if hasattr(scene_config, 'antenna_config') and scene_config.antenna_config == AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV:
        rx_mask = 15
        tx_mask = 5  # Use TX1 and TX3 only (binary 101), matching working profile
    cfg_lines.append(f"channelCfg {rx_mask} {tx_mask} 0")
    cfg_lines.append("adcCfg 2 1")
    cfg_lines.append("adcbufCfg -1 0 1 1 1")
    # Place lowPower here, as in reference profile
    cfg_lines.append("lowPower 0 0")

    # Profile config for AWR6843ISK (TI order):
    # profileCfg <profileId> <startFreq> <idleTime> <adcStartTime> <rampEndTime> <txOutPower> <txPhaseShifter> <freqSlopeConst> <numAdcSamples> <digOutSampleRate> <hpfCornerFreq1> <hpfCornerFreq2> <rxGain>
    profile_id = 0
    start_freq = getattr(scene_config, 'profile_start_freq_ghz', 60.0)  # GHz
    idle_time = getattr(scene_config, 'profile_idle_time_us', 7.0)      # us
    adc_start_time = getattr(scene_config, 'profile_adc_start_time_us', 3.0)  # us
    ramp_end_time = getattr(scene_config, 'profile_ramp_end_time_us', 24.0)   # us
    tx_out_power = getattr(scene_config, 'profile_tx_out_power_db', 0)        # dB
    tx_phase_shifter = getattr(scene_config, 'profile_tx_phase_shifter_deg', 0) # deg
    freq_slope_const = getattr(scene_config, 'profile_freq_slope_mhz_us', 166.0) # MHz/us
    num_adc_samples = getattr(scene_config, 'profile_num_adc_samples', 256)     # int
    dig_out_sample_rate = getattr(scene_config, 'profile_dig_out_sample_rate_ksps', 12500) # ksps
    hpf_corner_freq1 = getattr(scene_config, 'profile_hpf_corner_freq1', 0)     # 0=175kHz, 1=235kHz, 2=350kHz, 3=700kHz
    hpf_corner_freq2 = getattr(scene_config, 'profile_hpf_corner_freq2', 0)     # 0=350kHz, 1=700kHz, 2=1.4MHz, 3=2.8MHz
    rx_gain = getattr(scene_config, 'profile_rx_gain_db', 158)                  # dB (max 158 for reference)
    cfg_lines.append(
        f"profileCfg {profile_id} {start_freq:.0f} {idle_time:.0f} {adc_start_time:.0f} {ramp_end_time:.0f} "
        f"{tx_out_power} {tx_phase_shifter} {freq_slope_const:.0f} 1 {num_adc_samples} "
        f"{dig_out_sample_rate} {hpf_corner_freq1} {hpf_corner_freq2} {rx_gain}"
    )

    # Chirp config (2 chirps for TX1 and TX3, matching working profile)
    for i, tx in enumerate([1, 4]):  # TX1 and TX3 only
        cfg_lines.append(f"chirpCfg {i} {i} 0 0 0 0 0 {tx}")

    # Frame config
    frame_chirp_start_idx = getattr(scene_config, 'frame_chirp_start_idx', 0)
    frame_chirp_end_idx = 1  # Use chirps 0-1 (2 chirps total), matching working profile
    num_loops = getattr(scene_config, 'frame_num_loops', 32)  # Use 32 loops, matching working profile
    num_frames = getattr(scene_config, 'frame_num_frames', 0)
    frame_periodicity_ms = 1000.0 / getattr(scene_config, 'frame_rate_fps', 10.0)
    trigger_select = getattr(scene_config, 'frame_trigger_select', 1)
    trigger_delay_ms = getattr(scene_config, 'frame_trigger_delay_ms', 0)
    cfg_lines.append(
        f"frameCfg {frame_chirp_start_idx} {frame_chirp_end_idx} {num_loops} {num_frames} "
        f"{frame_periodicity_ms:.2f} {trigger_select} {trigger_delay_ms}"
    )

    # guiMonitor
    detected_objects = 1 if getattr(scene_config, 'plot_scatter', True) or getattr(scene_config, 'plot_statistics', True) else 0
    log_mag_range = 1 if getattr(scene_config, 'plot_range_profile', True) else 0
    noise_profile = 1 if getattr(scene_config, 'plot_noise_profile', False) else 0
    range_azimuth_heat_map = 1 if getattr(scene_config, 'plot_range_azimuth_heat_map', False) else 0
    range_doppler_heat_map = 1 if getattr(scene_config, 'plot_range_doppler_heat_map', False) else 0
    stats_info = 1 if getattr(scene_config, 'plot_statistics', True) else 0
    cfg_lines.append(
        f"guiMonitor -1 {detected_objects} {log_mag_range} {noise_profile} "
        f"{range_azimuth_heat_map} {range_doppler_heat_map} {stats_info}"
    )

    # --- Always include all required/advanced commands, using defaults if not set ---
    # multiObjBeamForming
    mobf = getattr(scene_config, 'multi_obj_beam_forming', None)
    if mobf:
        if isinstance(mobf, dict):
            cfg_lines.append(f"multiObjBeamForming {mobf.get('subframe_idx', -1)} {mobf.get('enabled', 1)} {mobf.get('threshold', 0.5)}")
        else:
            cfg_lines.append(f"multiObjBeamForming {getattr(mobf, 'subframe_idx', -1)} {getattr(mobf, 'enabled', 1)} {getattr(mobf, 'threshold', 0.5)}")
    else:
        cfg_lines.append("multiObjBeamForming -1 1 0.5")
    # cfarCfg (at least 2)
    cfar_cfgs = getattr(scene_config, 'cfar_cfgs', [])
    if not cfar_cfgs:
        cfar_cfgs = [
            {'subframe_idx': -1, 'proc_direction': 0, 'average_mode': 2, 'win_len': 8, 'guard_len': 4, 'noise_div': 3, 'cyclic_mode': 0, 'threshold_scale': 15.0, 'peak_grouping_en': 0},
            {'subframe_idx': -1, 'proc_direction': 1, 'average_mode': 0, 'win_len': 4, 'guard_len': 2, 'noise_div': 3, 'cyclic_mode': 1, 'threshold_scale': 15.0, 'peak_grouping_en': 0}
        ]
    for cfar in cfar_cfgs:
        cfg_lines.append(
            f"cfarCfg {cfar.get('subframe_idx', -1)} {cfar.get('proc_direction', 0)} {cfar.get('average_mode', 2)} "
            f"{cfar.get('win_len', 8)} {cfar.get('guard_len', 4)} {cfar.get('noise_div', 3)} {cfar.get('cyclic_mode', 0)} "
            f"{cfar.get('threshold_scale', 15.0)} {cfar.get('peak_grouping_en', 0)}"
        )
    # calibDcRangeSig
    cdrs = getattr(scene_config, 'calib_dc_range_sig', None)
    if not cdrs:
        cdrs = {'subframe_idx': -1, 'enabled': 0, 'negative_bin_idx': -5, 'positive_bin_idx': 8, 'num_avg_frames': 256}
    if isinstance(cdrs, dict):
        cfg_lines.append(
            f"calibDcRangeSig {cdrs.get('subframe_idx', -1)} {cdrs.get('enabled', 0)} {cdrs.get('negative_bin_idx', -5)} "
            f"{cdrs.get('positive_bin_idx', 8)} {cdrs.get('num_avg_frames', 256)}"
        )
    else:
        cfg_lines.append(
            f"calibDcRangeSig {getattr(cdrs, 'subframe_idx', -1)} {getattr(cdrs, 'enabled', 0)} {getattr(cdrs, 'negative_bin_idx', -5)} "
            f"{getattr(cdrs, 'positive_bin_idx', 8)} {getattr(cdrs, 'num_avg_frames', 256)}"
        )
    # clutterRemoval
    cfg_lines.append("clutterRemoval -1 0")
    # compRangeBiasAndRxChanPhase
    comp = getattr(scene_config, 'comp_range_bias_and_rx_chan_phase', None)
    if not comp:
        comp = [0.0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    cfg_lines.append(f"compRangeBiasAndRxChanPhase {' '.join(str(v) for v in comp)}")
    # measureRangeBiasAndRxChanPhase
    meas = getattr(scene_config, 'measure_range_bias_and_rx_chan_phase', None)
    if not meas:
        meas = [0, 1.0, 0.2]
    cfg_lines.append(f"measureRangeBiasAndRxChanPhase {' '.join(str(v) for v in meas)}")
    # aoaFovCfg
    aoa = getattr(scene_config, 'aoa_fov_cfg', None)
    if not aoa:
        aoa = {'subframe_idx': -1, 'min_azimuth_deg': -90, 'max_azimuth_deg': 90, 'min_elevation_deg': -90, 'max_elevation_deg': 90}
    cfg_lines.append(
        f"aoaFovCfg {aoa.get('subframe_idx', -1)} {aoa.get('min_azimuth_deg', -90)} {aoa.get('max_azimuth_deg', 90)} "
        f"{aoa.get('min_elevation_deg', -90)} {aoa.get('max_elevation_deg', 90)}"
    )
    # cfarFovCfg (at least 2)
    cfar_fov_cfgs = getattr(scene_config, 'cfar_fov_cfgs', [])
    if not cfar_fov_cfgs:
        cfar_fov_cfgs = [
            {'subframe_idx': -1, 'proc_direction': 0, 'min': 0.25, 'max': 9.0},
            {'subframe_idx': -1, 'proc_direction': 1, 'min': -20.16, 'max': 20.16}
        ]
    for cfar_fov in cfar_fov_cfgs:
        cfg_lines.append(
            f"cfarFovCfg {cfar_fov.get('subframe_idx', -1)} {cfar_fov.get('proc_direction', 0)} "
            f"{cfar_fov.get('min', 0.25)} {cfar_fov.get('max', 9.0)}"
        )
    # extendedMaxVelocity
    ext = getattr(scene_config, 'extended_max_velocity', None)
    if not ext:
        ext = {'subframe_idx': -1, 'enabled': 0}
    cfg_lines.append(f"extendedMaxVelocity {ext.get('subframe_idx', -1)} {ext.get('enabled', 0)}")
    # CQRxSatMonitor
    cqrx = getattr(scene_config, 'cq_rx_sat_monitor', None)
    if not cqrx:
        cqrx = {'profile_id': 0, 'sat_mon_sel': 3, 'pri_slice': 4, 'num_slices': 63, 'rx_chan_mask': 0}
    cfg_lines.append(
        f"CQRxSatMonitor {cqrx.get('profile_id', 0)} {cqrx.get('sat_mon_sel', 3)} {cqrx.get('pri_slice', 4)} "
        f"{cqrx.get('num_slices', 63)} {cqrx.get('rx_chan_mask', 0)}"
    )
    # CQSigImgMonitor
    cqsi = getattr(scene_config, 'cq_sig_img_monitor', None)
    if not cqsi:
        cqsi = {'profile_id': 0, 'num_slices': 127, 'rx_chan_mask': 4}
    cfg_lines.append(
        f"CQSigImgMonitor {cqsi.get('profile_id', 0)} {cqsi.get('num_slices', 127)} {cqsi.get('rx_chan_mask', 4)}"
    )
    # analogMonitor
    analog = getattr(scene_config, 'analog_monitor', None)
    if not analog:
        analog = {'profile_id': 0, 'enable': 0}
    cfg_lines.append(f"analogMonitor {analog.get('profile_id', 0)} {analog.get('enable', 0)}")
    # lvdsStreamCfg
    lvds = getattr(scene_config, 'lvds_stream_cfg', None)
    if not lvds:
        lvds = {'subframe_idx': -1, 'enable_header': 0, 'data_fmt': 0, 'enable_sw': 0}
    cfg_lines.append(
        f"lvdsStreamCfg {lvds.get('subframe_idx', -1)} {lvds.get('enable_header', 0)} {lvds.get('data_fmt', 0)} {lvds.get('enable_sw', 0)}"
    )
    # bpmCfg
    bpm = getattr(scene_config, 'bpm_cfg', None)
    if not bpm:
        bpm = {'subframe_idx': -1, 'enabled': 0, 'start_idx': 0, 'end_idx': 0}
    cfg_lines.append(
        f"bpmCfg {bpm.get('subframe_idx', -1)} {bpm.get('enabled', 0)} {bpm.get('start_idx', 0)} {bpm.get('end_idx', 0)}"
    )
    # calibData
    calib = getattr(scene_config, 'calib_data', None)
    if not calib:
        calib = {'profile_id': 0, 'enabled': 0, 'reserved': 0}
    cfg_lines.append(
        f"calibData {calib.get('profile_id', 0)} {calib.get('enabled', 0)} {calib.get('reserved', 0)}"
    )

    return "\n".join(cfg_lines) 