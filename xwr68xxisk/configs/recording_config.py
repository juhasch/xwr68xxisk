"""Recording configuration for radar data."""

from typing import List, Literal
from pydantic import Field, validator, BaseModel, field_validator
from .base_config import BaseConfig

class RecordingConfig(BaseModel):
    """Configuration for radar data recording."""
    enabled: bool = Field(
        default=True,
        description="Whether recording is enabled"
    )
    formats: List[str] = Field(
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
    buffer_size: int = Field(
        default=1000,
        description="Number of frames to buffer in memory"
    )
    
    @field_validator('formats')
    @classmethod
    def validate_formats(cls, v: List[str]) -> List[str]:
        """Validate recording formats."""
        valid_formats = ["csv", "pcd"]
        for fmt in v:
            if fmt.lower() not in valid_formats:
                raise ValueError(f"Invalid format: {fmt}. Must be one of {valid_formats}")
        return [fmt.lower() for fmt in v]
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"RecordingConfig(enabled={self.enabled}, "
            f"formats={self.formats}, "
            f"prefix='{self.prefix}', "
            f"directory='{self.directory}', "
            f"buffer_size={self.buffer_size})"
        ) 