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

# --- New Models for Scene Configuration GUI ---

class AntennaConfigEnum(str, Enum):
    CFG_4RX_3TX_15DEG_ELEV = "4Rx,3Tx(15 deg + Elevation)"
    # Add other antenna configurations as Enum members if available
    # Example: CFG_2RX_1TX_30DEG = "2Rx,1Tx(30 deg)"

class DesirableConfigEnum(str, Enum):
    BEST_RANGE_RESOLUTION = "Best Range Resolution"
    BEST_VELOCITY_RESOLUTION = "Best Velocity Resolution"
    BEST_RANGE = "Best Range"
    # Add other desirable configurations as Enum members

class SceneProfileConfig(BaseModel):
    """
    Configuration model representing the state of the Scene Selection GUI.
    """
    model_config = ConfigDict(use_enum_values=True)

    # Top selections
    antenna_config: AntennaConfigEnum = Field(
        AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV, 
        description="Selected antenna configuration preset."
    )
    desirable_config: DesirableConfigEnum = Field(
        DesirableConfigEnum.BEST_RANGE_RESOLUTION,
        description="Selected desirable configuration preset (e.g., best range resolution)."
    )

    # Scene Selection sliders and inputs
    frame_rate_fps: float = Field(
        10.0, 
        ge=1.0, 
        le=30.0, 
        description="Frame Rate in frames per second (fps)."
    )
    range_resolution_m: float = Field(
        0.044, 
        ge=0.039, 
        le=0.047, 
        description="Desired range resolution in meters (m)."
    )
    max_unambiguous_range_m: float = Field(
        9.02, 
        ge=3.95, 
        le=18.02, 
        description="Maximum unambiguous range in meters (m)."
    )
    max_radial_velocity_ms: float = Field(
        1.0, # Value from image appears to be 1.0 for this specific combination
        ge=0.27, 
        le=6.39, 
        description="Maximum radial velocity in meters per second (m/s)."
    )
    # This is often a calculated/derived value, but GUI shows an input.
    # For the model, it's a float. GUI can decide if it's editable or display-only.
    radial_velocity_resolution_ms: float = Field(
        0.13, 
        description="Desired radial velocity resolution in m/s. May be auto-calculated or selected."
    )

    # Detailed Profile Parameters (populated with defaults from config_generator.py)
    profile_start_freq_ghz: float = Field(
        60.25, description="Profile: Start Frequency in GHz."
    )
    profile_idle_time_us: float = Field(
        7.0, description="Profile: Idle Time in microseconds."
    )
    profile_adc_start_time_us: float = Field(
        6.0, description="Profile: ADC Start Time in microseconds."
    )
    profile_ramp_end_time_us: float = Field(
        60.0, description="Profile: Ramp End Time in microseconds."
    )
    profile_tx_out_power_db: int = Field(
        0, description="Profile: TX Output Power back-off in dB (0 for max power)."
    )
    profile_tx_phase_shifter_deg: int = Field(
        0, description="Profile: TX Phase Shifter in degrees."
    )
    profile_freq_slope_mhz_us: float = Field(
        20.0, description="Profile: Frequency Slope in MHz/microsecond."
    )
    profile_tx_start_time_us: float = Field(
        1.0, description="Profile: TX Start Time in microseconds."
    )
    profile_num_adc_samples: int = Field(
        256, description="Profile: Number of ADC Samples."
    )
    profile_dig_out_sample_rate_ksps: int = Field(
        5000, description="Profile: Digital Output Sample Rate in kSPS."
    )
    profile_hpf_corner_freq1: int = Field(
        0, description="Profile: HPF1 Corner Frequency (0: 175KHz, 1: 235KHz, 2: 350KHz, 3: 700KHz)."
    )
    profile_hpf_corner_freq2: int = Field(
        0, description="Profile: HPF2 Corner Frequency (0: 350KHz, 1: 700KHz, 2: 1.4MHz, 3: 2.8MHz)."
    )
    profile_rx_gain_db: int = Field(
        30, description="Profile: RX Gain in dB."
    )

    # Frame Config Parameters
    frame_num_loops: int = Field(
        64, description="Frame: Number of loops (Doppler Bins)."
    )
    frame_num_frames: int = Field(
        0, description="Frame: Number of frames to transmit (0 for infinite)."
    )
    frame_trigger_select: int = Field(
        1, description="Frame: Trigger select (1 for software trigger, 2 for hardware trigger)."
    )
    frame_trigger_delay_ms: int = Field(
        0, description="Frame: Trigger delay in milliseconds."
    )
    frame_chirp_start_idx: int = Field(
        0, description="Frame: Chirp Start Index."
    )

    # Plot Selection checkboxes
    plot_scatter: bool = Field(True, description="Enable Scatter Plot.")
    plot_range_profile: bool = Field(True, description="Enable Range Profile plot.")
    plot_noise_profile: bool = Field(False, description="Enable Noise Profile plot.")
    plot_range_azimuth_heat_map: bool = Field(False, description="Enable Range Azimuth Heat Map.")
    plot_range_doppler_heat_map: bool = Field(False, description="Enable Range Doppler Heat Map.")
    plot_statistics: bool = Field(True, description="Enable Statistics display.")

    @field_validator('antenna_config', mode='before')
    @classmethod
    def validate_antenna_config(cls, v: Any) -> AntennaConfigEnum:
        """Validate antenna configuration."""
        if isinstance(v, str):
            try:
                return AntennaConfigEnum(v)
            except ValueError:
                # If the string doesn't match any enum value, return the default
                return AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV
        return v

    @field_validator('profile_num_adc_samples')
    @classmethod
    def round_adc_samples_to_power_of_2(cls, v: int) -> int:
        """Ensure num_adc_samples is a power of 2, rounding up if necessary."""
        if v <= 0: # Or raise ValueError for non-positive
            return 1 # Smallest power of 2
        power_of_2 = 1
        while power_of_2 < v:
            power_of_2 *= 2
        return power_of_2

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
    default_scene_config = SceneProfileConfig()
    print("Default Scene Configuration:")
    print(default_scene_config.json(indent=2))

    custom_scene_config = SceneProfileConfig(
        antenna_config=AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV,
        desirable_config=DesirableConfigEnum.BEST_VELOCITY_RESOLUTION,
        frame_rate_fps=20,
        range_resolution_m=0.040,
        max_unambiguous_range_m=15.0,
        max_radial_velocity_ms=5.0,
        radial_velocity_resolution_ms=0.10,
        plot_range_doppler_heat_map=True,
        plot_scatter=False
    )
    print("\nCustom Scene Configuration:")
    print(custom_scene_config.json(indent=2)) 