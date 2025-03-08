from enum import IntEnum
from typing import List, Optional
from pydantic import BaseModel, Field, conint, confloat

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
    log_mag_range: bool = Field(..., description="Log magnitude range")
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

class RadarConfig(BaseModel):
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