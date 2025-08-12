"""Tracking configuration for radar point cloud processing."""

from pydantic import BaseModel, Field, field_validator
from .base_config import BaseConfig

class TrackingConfig(BaseModel):
    """Configuration for point cloud tracking."""
    enabled: bool = Field(
        default=False,
        description="Whether tracking is enabled"
    )
    max_distance: float = Field(
        default=2.0,
        ge=0.5,
        le=5.0,
        description="Maximum distance for track association (meters)"
    )
    min_hits: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Minimum hits before track is confirmed"
    )
    max_misses: int = Field(
        default=5,
        ge=2,
        le=10,
        description="Maximum misses before track is dropped"
    )
    dt: float = Field(
        default=0.1,
        ge=0.01,
        le=1.0,
        description="Time step between frames (seconds)"
    )
    
    @field_validator('max_misses')
    @classmethod
    def validate_max_misses(cls, v: int) -> int:
        """Validate max_misses is positive."""
        if v < 1:
            raise ValueError("max_misses must be at least 1")
        return v
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"TrackingConfig(enabled={self.enabled}, "
            f"max_distance={self.max_distance:.2f}m, "
            f"min_hits={self.min_hits}, "
            f"max_misses={self.max_misses}, "
            f"dt={self.dt:.3f}s)"
        ) 