"""Configuration manager for radar application."""

from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import Field, BaseModel
import logging
import shutil
from datetime import datetime
from .base_config import BaseConfig, enum_to_value
from .clustering_config import ClusteringConfig
from .tracking_config import TrackingConfig
from .gui_config import DisplayConfig, ProcessingConfig
from .recording_config import RecordingConfig
from .camera_config import CameraConfig
from ..radar_config_models import RadarConfig

logger = logging.getLogger(__name__)

class MainConfig(BaseConfig):
    """Main configuration class that combines all sub-configurations."""
    version: str = Field(
        default="1.0",
        pattern="^\\d+\\.\\d+$",
        description="Configuration version"
    )
    radar: RadarConfig
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    recording: RecordingConfig = Field(default_factory=RecordingConfig)
    camera: CameraConfig = Field(default_factory=CameraConfig)

class ConfigManager:
    """Manages loading, saving, and updating configurations."""
    
    def __init__(self, config_dir: Optional[str | Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Directory containing configuration files.
                       If None, uses default config directory.
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Use 'configs' directory in project root
            self.config_dir = Path("configs")
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.current_config: Optional[MainConfig] = None
    
    def _create_backup(self, config_path: Path) -> None:
        """Create a backup of the configuration file.
        
        Args:
            config_path: Path to the configuration file
        """
        if config_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = config_path.parent / f"{config_path.stem}_{timestamp}{config_path.suffix}"
            shutil.copy2(config_path, backup_path)
            logger.info(f"Created backup of configuration at {backup_path}")
    
    def load_config(self, config_name: str = "default_config.yaml") -> MainConfig:
        """Load configuration from file.
        
        Args:
            config_name: Name of the configuration file
            
        Returns:
            Loaded configuration
            
        Raises:
            FileNotFoundError: If configuration file doesn't exist
            ValueError: If configuration is invalid
        """
        config_path = self.config_dir / config_name
        
        try:
            self.current_config = MainConfig.from_yaml(config_path)
            logger.info(f"Loaded configuration from {config_path}")
            return self.current_config
        except FileNotFoundError:
            logger.warning(f"Configuration file {config_path} not found, creating default")
            self.current_config = self._create_default_config()
            self.save_config(config_name)
            return self.current_config
    
    def save_config(self, config_name: str = "default_config.yaml") -> None:
        """Save current configuration to file.
        
        Args:
            config_name: Name of the configuration file
            
        Raises:
            RuntimeError: If no configuration is loaded
        """
        if not self.current_config:
            raise RuntimeError("No configuration loaded")
            
        config_path = self.config_dir / config_name
        # self._create_backup(config_path) # Commented out to prevent backup creation
        # Patch: ensure enums are converted to values before YAML serialization
        import yaml
        data = self.current_config.model_dump()
        data = enum_to_value(data)
        with open(config_path, 'w') as f:
            yaml.safe_dump(data, f, default_flow_style=False)
        logger.info(f"Saved configuration to {config_path}")
    
    def update_config(self, updates: Dict[str, Any]) -> MainConfig:
        """Update current configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
            
        Returns:
            Updated configuration
            
        Raises:
            RuntimeError: If no configuration is loaded
            ValueError: If updates are invalid
        """
        if not self.current_config:
            raise RuntimeError("No configuration loaded")
            
        try:
            self.current_config = self.current_config.update(updates)
            logger.info("Configuration updated successfully")
            return self.current_config
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            raise
    
    def _create_default_config(self) -> MainConfig:
        """Create default configuration."""
        from ..radar_config_models import (
            RadarConfig, DfeDataOutputModeConfig, ModeType, ChannelConfig, AdcConfig, AdcBits, AdcOutputFormat,
            AdcBufConfig, ProfileConfig, CalibDcRangeSigConfig, ClutterRemovalConfig, AoaFovConfig, CfarConfig,
            MultiObjBeamFormingConfig, GuiMonitorConfig, AnalogMonitorConfig, LvdsStreamConfig
        )
        return MainConfig(
            version="1.0",
            radar=RadarConfig(
                dfe_data_output_mode=DfeDataOutputModeConfig(mode_type=ModeType.FRAME_BASED_CHIRPS),
                channel_cfg=ChannelConfig(rx_channel_en=15, tx_channel_en=7, cascading=0),
                adc_cfg=AdcConfig(num_adc_bits=AdcBits.BITS_16, adc_output_fmt=AdcOutputFormat.COMPLEX_FILTERED),
                adc_buf_cfg=AdcBufConfig(subframe_idx=-1, adc_output_fmt=0, sample_swap=1, chan_interleave=1, chirp_threshold=4),
                profile_cfg=ProfileConfig(
                    profile_id=0, start_freq=60.0, idle_time=7.0, adc_start_time=3.0, ramp_end_time=24.0,
                    tx_out_power=0, tx_phase_shifter=0, freq_slope_const=166.0, tx_start_time=1.0,
                    num_adc_samples=256, dig_out_sample_rate=12500, hpf_corner_freq1=0, hpf_corner_freq2=0, rx_gain=30.0
                ),
                calib_dc_range_sig=CalibDcRangeSigConfig(subframe_idx=-1, enabled=False, negative_bin_idx=-5, positive_bin_idx=8, num_avg_frames=256),
                clutter_removal=ClutterRemovalConfig(subframe_idx=-1, enabled=False),
                aoa_fov_cfg=AoaFovConfig(subframe_idx=-1, min_azimuth_deg=-90.0, max_azimuth_deg=90.0, min_elevation_deg=-90.0, max_elevation_deg=90.0),
                cfar_cfg=CfarConfig(subframe_idx=-1, proc_direction=0, average_mode=2, win_len=8, guard_len=4, noise_div=3, cyclic_mode=0, threshold_scale=15.0, peak_grouping_en=False),
                multi_obj_beam_forming=MultiObjBeamFormingConfig(subframe_idx=-1, enabled=False, threshold=0.5),
                gui_monitor=GuiMonitorConfig(detected_objects=1, log_mag_range=True, noise_profile=False, range_azimuth_heat_map=False, range_doppler_heat_map=False, stats_info=True),
                analog_monitor=AnalogMonitorConfig(rx_saturation=False, sig_img_band=False),
                lvds_stream_cfg=LvdsStreamConfig(subframe_idx=-1, enable_header=False, data_fmt=0, enable_sw=False)
            ).model_dump(),
            clustering=ClusteringConfig(),
            tracking=TrackingConfig(),
            display=DisplayConfig(),
            processing=ProcessingConfig(),
            recording=RecordingConfig(),
            camera=CameraConfig()
        ) 
