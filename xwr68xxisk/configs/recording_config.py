"""Recording configuration for radar data."""

from typing import List, Literal
from pydantic import Field, validator
from .base_config import BaseConfig

class RecordingConfig(BaseConfig):
    """Configuration for radar data recording."""
    enabled: bool = Field(
        default=True,
        description="Whether recording is enabled"
    )
    formats: List[Literal['csv', 'pcd']] = Field(
        default=['csv'],
        description="List of formats to save data in ('csv' and/or 'pcd')"
    )
    prefix: str = Field(
        default="radar_data",
        description="Prefix for recorded data files"
    )
    directory: str = Field(
        default="recordings",
        description="Directory to save recordings in"
    )
    buffer_in_memory: bool = Field(
        default=False,
        description="Whether to buffer data in memory before saving"
    )
    
    @validator('formats')
    def validate_formats(cls, v):
        """Validate that at least one format is specified."""
        if not v:
            raise ValueError("At least one format must be specified")
        for fmt in v:
            if fmt not in ['csv', 'pcd']:
                raise ValueError(f"Unsupported format: {fmt}")
        return v
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"RecordingConfig(enabled={self.enabled}, "
            f"formats={self.formats}, "
            f"prefix='{self.prefix}', "
            f"directory='{self.directory}', "
            f"buffer_in_memory={self.buffer_in_memory})"
        ) 