"""Configuration manager for radar application."""

from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import Field, BaseModel
import logging
import shutil
from datetime import datetime
from .base_config import BaseConfig
from .clustering_config import ClusteringConfig
from .tracking_config import TrackingConfig
from .gui_config import DisplayConfig, ProcessingConfig
from .recording_config import RecordingConfig
from .camera_config import CameraConfig
from ..config import RadarConfig, ProfileConfig, FrameConfig

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
        self._create_backup(config_path)
        self.current_config.to_yaml(config_path)
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
        return MainConfig(
            version="1.0",
            radar=RadarConfig(
                num_doppler_bins=16,
                num_range_bins=256,
                range_resolution=0.1,
                range_idx_to_meters=0.1,
                doppler_resolution=0.1,
                max_range=10.0,
                max_velocity=5.0
            ),
            clustering=ClusteringConfig(),
            tracking=TrackingConfig(),
            display=DisplayConfig(),
            processing=ProcessingConfig(),
            recording=RecordingConfig(),
            camera=CameraConfig()
        ) 
