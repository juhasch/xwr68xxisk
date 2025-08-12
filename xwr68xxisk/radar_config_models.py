from enum import IntEnum, Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field, conint, confloat, field_validator, ConfigDict

class ModeType(IntEnum):
    FRAME_BASED_CHIRPS = 1
    CONTINUOUS_CHIRPING = 2
    ADVANCED_FRAME = 3

class AdcOutputFormat(IntEnum):
    REAL = 0
    COMPLEX_FILTERED = 1
    COMPLEX_UNFILTERED = 2

class AdcBits(IntEnum):
    BITS_12 = 0
    BITS_14 = 1
    BITS_16 = 2

class DfeDataOutputModeConfig(BaseModel):
    mode_type: ModeType = Field(..., description="Mode type for chirp configuration")

class ChannelConfig(BaseModel):
    rx_channel_en: int = Field(..., description="Receive antenna mask, e.g., 0x1111b = 15 for 4 antennas")
    tx_channel_en: int = Field(..., description="Transmit antenna mask")
    cascading: int = Field(0, description="SoC cascading, not applicable, set to 0")

class AdcConfig(BaseModel):
    num_adc_bits: AdcBits = Field(..., description="ADC resolution")
    adc_output_fmt: AdcOutputFormat = Field(..., description="ADC output format")

class AdcBufConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe Index, -1 for legacy mode")
    adc_output_fmt: int = Field(0, description="0 - Complex, 1 - Real")
    sample_swap: int = Field(1, description="0 - I in LSB, Q in MSB, 1 - Q in LSB, I in MSB")
    chan_interleave: int = Field(1, description="0 - interleaved, 1 - non-interleaved")
    chirp_threshold: conint(ge=0, le=8) = Field(..., description="Threshold for buffer switch (0-8)")

class ProfileConfig(BaseModel):
    profile_id: int = Field(..., description="Profile Identifier")
    start_freq: confloat(gt=0) = Field(..., description="Frequency Start in GHz")
    idle_time: confloat(ge=0) = Field(..., description="Idle Time in μs")
    adc_start_time: confloat(ge=0) = Field(..., description="ADC Valid Start Time in μs")
    ramp_end_time: confloat(ge=0) = Field(..., description="Ramp End Time in μs")
    tx_out_power: int = Field(0, description="TX power back-off code")
    tx_phase_shifter: int = Field(0, description="TX phase shifter")
    freq_slope_const: confloat(gt=0) = Field(..., description="Freq slope (MHz/μs)")
    tx_start_time: confloat(ge=0) = Field(..., description="TX Start Time (μs)")
    num_adc_samples: int = Field(..., description="ADC sample count")
    dig_out_sample_rate: int = Field(..., description="ADC freq (ksps)")
    hpf_corner_freq1: int = Field(..., description="HPF1 settings: 175/235/350/700 KHz")
    hpf_corner_freq2: int = Field(..., description="HPF2 settings: 350/700/1400/2800 KHz")
    rx_gain: float = Field(..., description="RX gain (dB)")

class CalibDcRangeSigConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    enabled: bool = Field(..., description="Enable/disable calibration")
    negative_bin_idx: int = Field(..., description="Negative bin index")
    positive_bin_idx: int = Field(..., description="Positive bin index")
    num_avg_frames: int = Field(..., description="Number of frames to average")

class ClutterRemovalConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    enabled: bool = Field(..., description="Enable/disable clutter removal")

class AoaFovConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    min_azimuth_deg: float = Field(..., description="Minimum azimuth in degrees")
    max_azimuth_deg: float = Field(..., description="Maximum azimuth in degrees")
    min_elevation_deg: float = Field(..., description="Minimum elevation in degrees")
    max_elevation_deg: float = Field(..., description="Maximum elevation in degrees")

class CfarConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    proc_direction: int = Field(..., description="0: range, 1: doppler")
    average_mode: int = Field(..., description="Averaging mode")
    win_len: int = Field(..., description="Window length")
    guard_len: int = Field(..., description="Guard length")
    noise_div: int = Field(..., description="Noise divider")
    cyclic_mode: int = Field(..., description="Cyclic mode")
    threshold_scale: float = Field(..., description="Threshold scale")
    peak_grouping_en: bool = Field(..., description="Peak grouping enable")

class MultiObjBeamFormingConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    enabled: bool = Field(..., description="Enable/disable")
    threshold: float = Field(..., description="Detection threshold")

class GuiMonitorConfig(BaseModel):
    detected_objects: int = Field(..., description="0: None, 1: Objects + side info, 2: Objects only")
    range_profile_enabled: bool = Field(True, description="Enable range profile output")
    range_profile_mode: str = Field("log_magnitude", description="Range profile mode: 'log_magnitude' or 'complex'")
    noise_profile: bool = Field(..., description="Noise floor profile")
    range_azimuth_heat_map: bool = Field(..., description="Range-azimuth heat map")
    range_doppler_heat_map: bool = Field(..., description="Range-Doppler heat map")
    stats_info: bool = Field(..., description="Statistics information")

class AnalogMonitorConfig(BaseModel):
    rx_saturation: bool = Field(..., description="RX saturation monitoring")
    sig_img_band: bool = Field(..., description="Signal image band monitoring")

class LvdsStreamConfig(BaseModel):
    subframe_idx: int = Field(..., description="Subframe index")
    enable_header: bool = Field(..., description="Enable header")
    data_fmt: int = Field(..., description="Data format")
    enable_sw: bool = Field(..., description="Enable software")

class AntennaConfigEnum(str, Enum):
    CFG_4RX_3TX_15DEG_ELEV = "4Rx,3Tx(15 deg + Elevation)"
    CFG_4RX_2TX_30DEG = "4Rx,2Tx(30 deg)"
    CFG_2RX_1TX_60DEG = "2Rx,1Tx(60 deg)"
    # Add other antenna configurations as needed

class RadarConfig(BaseModel):
    antenna_config: AntennaConfigEnum = Field(
        AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        description="Selected antenna configuration preset for GUI/scene selection. Not sent to radar as a command."
    )
    frame_rate_fps: float = Field(
        10.0,
        ge=1.0,
        le=30.0,
        description="Frame Rate in frames per second (fps) for GUI/scene selection. Not sent to radar as a command."
    )
    range_resolution_m: float = Field(
        0.044,
        ge=0.039,
        le=0.047,
        description="Desired range resolution in meters (m) for GUI/scene selection. Not sent to radar as a command."
    )
    max_unambiguous_range_m: float = Field(
        9.02,
        ge=3.95,
        le=18.02,
        description="Maximum unambiguous range in meters (m) for GUI/scene selection. Not sent to radar as a command."
    )
    max_radial_velocity_ms: float = Field(
        1.0,
        ge=0.27,
        le=6.39,
        description="Maximum radial velocity in meters per second (m/s) for GUI/scene selection. Not sent to radar as a command."
    )
    radial_velocity_resolution_ms: float = Field(
        0.13,
        description="Desired radial velocity resolution in m/s for GUI/scene selection. Not sent to radar as a command."
    )
    trigger_mode: int = Field(
        0,
        ge=0,
        le=2,
        description="Trigger mode: 0=timer-based (default), 1=software, 2=hardware"
    )
    plot_scatter: bool = Field(True, description="Enable Scatter Plot in GUI (not sent to radar)")
    plot_range_profile: bool = Field(True, description="Enable Range Profile plot in GUI (not sent to radar)")
    range_profile_mode: str = Field("log_magnitude", description="Range profile mode: 'log_magnitude' or 'complex'")
    plot_noise_profile: bool = Field(False, description="Enable Noise Profile plot in GUI (not sent to radar)")
    plot_range_azimuth_heat_map: bool = Field(False, description="Enable Range Azimuth Heat Map in GUI (not sent to radar)")
    plot_range_doppler_heat_map: bool = Field(False, description="Enable Range Doppler Heat Map in GUI (not sent to radar)")
    plot_statistics: bool = Field(True, description="Enable Statistics display in GUI (not sent to radar)")
    dfe_data_output_mode: DfeDataOutputModeConfig = Field(..., description="DFE data output mode configuration")
    channel_cfg: ChannelConfig = Field(..., description="Channel configuration")
    adc_cfg: AdcConfig = Field(..., description="ADC configuration")
    adc_buf_cfg: AdcBufConfig = Field(..., description="ADC buffer configuration")
    profile_cfg: ProfileConfig = Field(..., description="Profile configuration")
    calib_dc_range_sig: Optional[CalibDcRangeSigConfig] = Field(None, description="DC range calibration configuration")
    clutter_removal: Optional[ClutterRemovalConfig] = Field(None, description="Clutter removal configuration")
    aoa_fov_cfg: Optional[AoaFovConfig] = Field(None, description="Angle of Arrival FOV configuration")
    cfar_cfg: Optional[CfarConfig] = Field(None, description="CFAR detection configuration")
    multi_obj_beam_forming: Optional[MultiObjBeamFormingConfig] = Field(None, description="Multi-object beamforming configuration")
    gui_monitor: Optional[GuiMonitorConfig] = Field(None, description="GUI monitoring configuration")
    analog_monitor: Optional[AnalogMonitorConfig] = Field(None, description="Analog monitoring configuration")
    lvds_stream_cfg: Optional[LvdsStreamConfig] = Field(None, description="LVDS streaming configuration")
    cfar_cfgs: Optional[List[CfarConfig]] = Field(
        default_factory=list,
        description="List of CFAR configuration commands (advanced/expert mode, not sent to radar by default)"
    )
    comp_range_bias_and_rx_chan_phase: Optional[list] = Field(default=None, description="Range bias and RX channel phase compensation (advanced/expert mode, not sent to radar by default)")
    measure_range_bias_and_rx_chan_phase: Optional[list] = Field(default=None, description="Range bias and RX channel phase measurement (advanced/expert mode, not sent to radar by default)")
    aoa_fov_cfg: Optional[dict] = Field(default=None, description="Angle of Arrival FOV configuration (advanced/expert mode, not sent to radar by default)")
    cfar_fov_cfgs: Optional[list] = Field(default_factory=list, description="List of CFAR FOV configuration commands (advanced/expert mode, not sent to radar by default)")
    extended_max_velocity: Optional[dict] = Field(default=None, description="Extended max velocity configuration (advanced/expert mode, not sent to radar by default)")
    cq_rx_sat_monitor: Optional[dict] = Field(default=None, description="RX saturation monitor configuration (advanced/expert mode, not sent to radar by default)")
    cq_sig_img_monitor: Optional[dict] = Field(default=None, description="Signal image band monitor configuration (advanced/expert mode, not sent to radar by default)")
    analog_monitor: Optional[dict] = Field(default=None, description="Analog monitor configuration (advanced/expert mode, not sent to radar by default)")
    lvds_stream_cfg: Optional[dict] = Field(default=None, description="LVDS streaming configuration (advanced/expert mode, not sent to radar by default)")
    bpm_cfg: Optional[dict] = Field(default=None, description="BPM configuration (advanced/expert mode, not sent to radar by default)")
    calib_data: Optional[dict] = Field(default=None, description="Calibration data configuration (advanced/expert mode, not sent to radar by default)")

# --- New Models for Scene Configuration GUI ---

# Remove SceneProfileConfig, AntennaConfigEnum, DesirableConfigEnum, and their usages

class DisplayConfig(BaseModel):
    """Configuration for display settings.
    
    Attributes
    ----------
    plot_width : int
        Width of the plot in pixels
    plot_height : int
        Height of the plot in pixels
    x_range : tuple[float, float]
        Range of x-axis in meters
    y_range : tuple[float, float]
        Range of y-axis in meters
    """
    plot_width: int = 800
    plot_height: int = 600
    x_range: tuple[float, float] = (-5.0, 5.0)
    y_range: tuple[float, float] = (0.0, 10.0)

# Example usage (optional, can be removed or kept for testing)
if __name__ == "__main__":
    default_scene_config = RadarConfig() # Changed from SceneProfileConfig to RadarConfig
    print("Default Radar Configuration:")
    print(default_scene_config.json(indent=2))

    custom_scene_config = RadarConfig( # Changed from SceneProfileConfig to RadarConfig
        dfe_data_output_mode=DfeDataOutputModeConfig(mode_type=ModeType.FRAME_BASED_CHIRPS),
        channel_cfg=ChannelConfig(rx_channel_en=0x1111, tx_channel_en=0x1111, cascading=0),
        adc_cfg=AdcConfig(num_adc_bits=AdcBits.BITS_16, adc_output_fmt=AdcOutputFormat.COMPLEX_FILTERED),
        adc_buf_cfg=AdcBufConfig(subframe_idx=-1, adc_output_fmt=0, sample_swap=1, chan_interleave=1, chirp_threshold=4),
        profile_cfg=ProfileConfig(
            profile_id=1, start_freq=60.25, idle_time=7.0, adc_start_time=6.0, ramp_end_time=60.0,
            tx_out_power=0, tx_phase_shifter=0, freq_slope_const=20.0, tx_start_time=1.0,
            num_adc_samples=256, dig_out_sample_rate=5000, hpf_corner_freq1=0, hpf_corner_freq2=0, rx_gain=30.0
        ),
        calib_dc_range_sig=CalibDcRangeSigConfig(subframe_idx=0, enabled=True, negative_bin_idx=0, positive_bin_idx=0, num_avg_frames=10),
        clutter_removal=ClutterRemovalConfig(subframe_idx=0, enabled=True),
        aoa_fov_cfg=AoaFovConfig(subframe_idx=0, min_azimuth_deg=-90.0, max_azimuth_deg=90.0, min_elevation_deg=-90.0, max_elevation_deg=90.0),
        cfar_cfg=CfarConfig(subframe_idx=0, proc_direction=0, average_mode=0, win_len=16, guard_len=4, noise_div=1, cyclic_mode=0, threshold_scale=1.0, peak_grouping_en=True),
        multi_obj_beam_forming=MultiObjBeamFormingConfig(subframe_idx=0, enabled=True, threshold=0.1),
        gui_monitor=GuiMonitorConfig(detected_objects=1, range_profile_enabled=True, range_profile_mode="log_magnitude", noise_profile=True, range_azimuth_heat_map=True, range_doppler_heat_map=True, stats_info=True),
        analog_monitor=AnalogMonitorConfig(rx_saturation=True, sig_img_band=True),
        lvds_stream_cfg=LvdsStreamConfig(subframe_idx=0, enable_header=True, data_fmt=0, enable_sw=True)
    )
    print("\nCustom Radar Configuration:")
    print(custom_scene_config.json(indent=2)) 