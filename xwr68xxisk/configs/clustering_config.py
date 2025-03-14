"""Clustering configuration for radar point cloud processing."""

from pydantic import Field
from .base_config import BaseConfig

class ClusteringConfig(BaseConfig):
    """Configuration for point cloud clustering."""
    enabled: bool = Field(
        default=False,
        description="Whether clustering is enabled"
    )
    eps: float = Field(
        default=0.5,
        ge=0.1,
        le=2.0,
        description="Maximum distance between points in a cluster (meters)"
    )
    min_samples: int = Field(
        default=5,
        ge=3,
        le=20,
        description="Minimum number of points to form a cluster"
    )
    algorithm: str = Field(
        default="dbscan",
        pattern="^(dbscan)$",
        description="Clustering algorithm to use (currently only DBSCAN supported)"
    )
    
    def __str__(self) -> str:
        """Return human-readable string representation."""
        return (
            f"ClusteringConfig(enabled={self.enabled}, "
            f"eps={self.eps:.2f}m, "
            f"min_samples={self.min_samples}, "
            f"algorithm={self.algorithm})"
        ) 