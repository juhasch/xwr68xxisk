"""Base configuration classes and utilities."""

from pathlib import Path
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field, ConfigDict
import yaml
import enum
import logging

logger = logging.getLogger(__name__)

# Helper to recursively convert Enums to their .value
def enum_to_value(obj):
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: enum_to_value(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [enum_to_value(i) for i in obj]
    return obj

class BaseConfig(BaseModel):
    """Base configuration class with common functionality."""
    model_config = ConfigDict(frozen=True)  # Make configs immutable after creation
    
    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "BaseConfig":
        """Load configuration from YAML file."""
        try:
            with open(yaml_path, 'r') as f:
                config_dict = yaml.safe_load(f)
            if config_dict is None:
                raise ValueError(f"YAML file {yaml_path} is empty or invalid.")
            return cls.model_validate(config_dict)
        except Exception as e:
            logger.error(f"Error loading configuration from {yaml_path}: {e}")
            raise
    
    def to_yaml(self, yaml_path: str | Path) -> None:
        """Save configuration to YAML file."""
        try:
            with open(yaml_path, 'w') as f:
                data = self.model_dump()
                data = enum_to_value(data)
                yaml.safe_dump(data, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving configuration to {yaml_path}: {e}")
            raise
    
    def update(self, updates: Dict[str, Any]) -> "BaseConfig":
        """Create a new configuration with updates applied."""
        current = self.model_dump()
        current.update(updates)
        return self.__class__.model_validate(current) 