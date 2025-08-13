"""GUI configuration for radar visualization."""

from typing import Tuple, Optional
from pydantic import Field, field_validator
from .base_config import BaseConfig

class DisplayConfig(BaseConfig):
    """Configuration for display parameters."""
    plot_width: int = Field(
        default=1100,
        ge=800,
        le=1920,
        description="Plot width in pixels"
    )
    plot_height: int = Field(
        default=600,
        ge=400,
        le=1080,
        description="Plot height in pixels"
    )
    x_range: Tuple[float, float] = Field(
        default=(-2.5, 2.5),
        description="X-axis range in meters (min, max)"
    )
    y_range: Tuple[float, float] = Field(
        default=(0, 5),
        description="Y-axis range in meters (min, max)"
    )
    update_period_ms: int = Field(
        default=10,
        ge=10,
        le=100,
        description="Plot update period in milliseconds"
    )
    
    @field_validator('x_range', 'y_range')
    @classmethod
    def validate_range(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        """Validate that range values are in ascending order."""
        if v[0] >= v[1]:
            raise ValueError("Range values must be in ascending order")
        return v

class ProcessingConfig(BaseConfig):
    """Configuration for radar signal processing."""
    clutter_removal: bool = Field(
        default=False,
        description="Whether static clutter removal is enabled"
    )
    mob_enabled: bool = Field(
        default=False,
        description="Whether multi-object beamforming is enabled"
    )
    mob_threshold: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="Multi-object beamforming threshold"
    )
    # Frame period is derived from sensor frame rate; remove from GUI config
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"ProcessingConfig(clutter_removal={self.clutter_removal}, "
            f"mob_enabled={self.mob_enabled}, "
            f"mob_threshold={self.mob_threshold:.2f})"
        ) 