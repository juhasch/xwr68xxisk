from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field, validator

class ProfileConfig(BaseModel):
    start_freq: int
    idle_time: int
    ramp_end_time: float
    freq_slope: float
    num_adc_samples: int
    dig_out_sample_rate: int

    @validator('num_adc_samples')
    def round_adc_samples_to_power_of_2(cls, v):
        power_of_2 = 1
        while power_of_2 < v:
            power_of_2 *= 2
        return power_of_2

class FrameConfig(BaseModel):
    chirp_start_idx: int
    chirp_end_idx: int
    num_loops: int
    frame_periodicity: int

    @property
    def num_chirps_per_frame(self) -> int:
        return (self.chirp_end_idx - self.chirp_start_idx + 1) * self.num_loops

class RadarConfig(BaseModel):
    """Model representing the calculated radar parameters"""
    num_doppler_bins: float
    num_range_bins: int
    range_resolution: float
    range_idx_to_meters: float
    doppler_resolution: float
    max_range: float
    max_velocity: float

    model_config = {"frozen": True}

class RadarConfigParser:
    """Parser for radar configuration files"""
    # Constants
    NUM_RX_ANT = 4
    NUM_TX_ANT = 3
    SPEED_OF_LIGHT = 3e8  # m/s

    @classmethod
    def parse_config_file(cls, config_path: str | Path) -> RadarConfig:
        """
        Parse a radar configuration file and extract key parameters.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            RadarConfig object containing calculated radar parameters
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If required configuration parameters are missing or invalid
        """
        try:
            with open(config_path) as f:
                config_lines = [line.strip() for line in f if line.strip() and not line.startswith('%')]
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        profile_data = {}
        frame_data = {}

        for line in config_lines:
            words = line.split()
            command = words[0]

            if command == "profileCfg":
                profile_data = {
                    "start_freq": int(float(words[2])),
                    "idle_time": int(words[3]),
                    "ramp_end_time": float(words[5]),
                    "freq_slope": float(words[8]),
                    "num_adc_samples": int(words[10]),
                    "dig_out_sample_rate": int(words[11])
                }
            elif command == "frameCfg":
                frame_data = {
                    "chirp_start_idx": int(words[1]),
                    "chirp_end_idx": int(words[2]),
                    "num_loops": int(words[3]),
                    "frame_periodicity": int(words[5])
                }

        try:
            profile = ProfileConfig(**profile_data)
            frame = FrameConfig(**frame_data)
        except Exception as e:
            raise ValueError(f"Invalid configuration data: {str(e)}")

        return cls._calculate_radar_parameters(profile, frame)

    @classmethod
    def _calculate_radar_parameters(cls, profile: ProfileConfig, frame: FrameConfig) -> RadarConfig:
        """Calculate radar parameters from profile and frame configurations"""
        return RadarConfig(
            num_doppler_bins=frame.num_chirps_per_frame / cls.NUM_TX_ANT,
            num_range_bins=profile.num_adc_samples,
            range_resolution=(
                cls.SPEED_OF_LIGHT * profile.dig_out_sample_rate * 1e3 /
                (2 * profile.freq_slope * 1e12 * profile.num_adc_samples)
            ),
            range_idx_to_meters=(
                cls.SPEED_OF_LIGHT * profile.dig_out_sample_rate * 1e3 /
                (2 * profile.freq_slope * 1e12 * profile.num_adc_samples)
            ),
            doppler_resolution=(
                cls.SPEED_OF_LIGHT / 
                (2 * profile.start_freq * 1e9 * 
                 (profile.idle_time + profile.ramp_end_time) * 1e-6 * 
                 (frame.num_chirps_per_frame / cls.NUM_TX_ANT) * cls.NUM_TX_ANT)
            ),
            max_range=(
                300 * 0.9 * profile.dig_out_sample_rate /
                (2 * profile.freq_slope * 1e3)
            ),
            max_velocity=(
                cls.SPEED_OF_LIGHT /
                (4 * profile.start_freq * 1e9 *
                 (profile.idle_time + profile.ramp_end_time) * 1e-6 * 
                 cls.NUM_TX_ANT)
            )
        )

def parse_config_file(config_path: str | Path) -> Dict[str, float]:
    """Legacy wrapper for backward compatibility"""
    config = RadarConfigParser.parse_config_file(config_path)
    return config.model_dump()

