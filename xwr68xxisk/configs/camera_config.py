"""Camera configuration settings."""

from enum import Enum
from typing import Optional
from pydantic import Field, BaseModel


class Resolution(BaseModel):
    """Camera resolution settings."""
    width: int = Field(
        default=640,
        ge=1,
        description="Width of the camera resolution in pixels"
    )
    height: int = Field(
        default=480,
        ge=1,
        description="Height of the camera resolution in pixels"
    )

class CameraConfig(BaseModel):
    """Camera configuration settings.
    
    This class defines the configuration parameters for the camera system.
    It supports different camera implementations and their specific settings.
    """
    implementation: str = Field(
        default="OpenCV",
        description="Camera implementation to use"
    )
    enabled: bool = Field(
        default=True,
        description="Whether the camera is enabled"
    )
    resolution: Resolution = Field(
        default_factory=Resolution,
        description="Camera resolution settings"
    )
    fps: int = Field(
        default=30,
        ge=1,
        le=120,
        description="Frames per second for camera capture"
    )
    device_id: Optional[int] = Field(
        default=None,
        description="Device ID for the camera (if multiple cameras are available)"
    ) 