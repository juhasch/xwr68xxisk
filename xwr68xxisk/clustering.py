"""Point cloud clustering module for radar data.

This module provides clustering algorithms for radar point cloud data,
including DBSCAN-based clustering optimized for radar point clouds.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from sklearn.cluster import DBSCAN
from xwr68xxisk.point_cloud import RadarPointCloud


@dataclass
class Cluster:
    """Class representing a cluster of points."""
    points: RadarPointCloud
    centroid: np.ndarray  # [x, y, z]
    velocity: float  # average radial velocity
    size: np.ndarray  # [width, height, depth]
    point_indices: np.ndarray  # indices of points in original point cloud
    metadata: Dict[str, Any] = None

    @property
    def num_points(self) -> int:
        """Get number of points in cluster."""
        return self.points.num_points


class PointCloudClustering:
    """Class to perform clustering on radar point cloud data."""
    
    def __init__(self, 
                 eps: float = 0.5,  # meters
                 min_samples: int = 5,
                 algorithm: str = 'dbscan'):
        """
        Initialize clustering algorithm.
        
        Args:
            eps: Maximum distance between points in a cluster (meters)
            min_samples: Minimum number of points to form a cluster
            algorithm: Clustering algorithm to use (currently only 'dbscan' supported)
        """
        self.eps = eps
        self.min_samples = min_samples
        self.algorithm = algorithm
        
        if algorithm != 'dbscan':
            raise ValueError("Currently only DBSCAN clustering is supported")
            
        self.clusterer = DBSCAN(
            eps=eps,
            min_samples=min_samples,
            algorithm='ball_tree',
            n_jobs=-1  # use all CPU cores
        )
        
    def cluster(self, point_cloud: RadarPointCloud) -> List[Cluster]:
        """
        Perform clustering on point cloud data.
        
        Args:
            point_cloud: RadarPointCloud object to cluster
            
        Returns:
            List of Cluster objects
        """
        if point_cloud.num_points < self.min_samples:
            return []
            
        # Get points in Cartesian coordinates and ensure they are finite
        points = point_cloud.get_cartesian_points()
        if len(points) == 0:
            return []
            
        # Remove any points with NaN or infinite values
        valid_mask = np.all(np.isfinite(points), axis=1)
        if not np.any(valid_mask):
            return []
            
        valid_points = points[valid_mask]
        valid_indices = np.where(valid_mask)[0]
        
        # Perform clustering
        labels = self.clusterer.fit_predict(valid_points)
        
        # Create clusters (excluding noise points labeled as -1)
        unique_labels = np.unique(labels)
        clusters = []
        
        for label in unique_labels:
            if label == -1:  # Skip noise points
                continue
                
            # Get indices of points in this cluster
            cluster_mask = labels == label
            cluster_indices = valid_indices[cluster_mask]
            
            # Get cluster points in Cartesian coordinates
            cluster_xyz = valid_points[cluster_mask]
            
            # Calculate cluster properties
            centroid = np.mean(cluster_xyz, axis=0)
            size = np.max(cluster_xyz, axis=0) - np.min(cluster_xyz, axis=0)
            
            # Calculate cluster volume (avoid zero volume)
            volume = max(np.prod(size), 1e-6)  # Use minimum volume to avoid division by zero
            density = len(cluster_indices) / volume
            
            # Extract cluster data using integer indices
            cluster_indices_list = cluster_indices.tolist()  # Convert to Python list
            mean_velocity = float(np.mean([point_cloud.velocity[i] for i in cluster_indices_list]))
            mean_snr = float(np.mean([point_cloud.snr[i] for i in cluster_indices_list]))
            mean_rcs = float(np.mean([point_cloud.rcs[i] for i in cluster_indices_list]))
            
            # Create point cloud for cluster points
            cluster_points = RadarPointCloud(
                range=np.array([point_cloud.range[i] for i in cluster_indices_list]),
                velocity=np.array([point_cloud.velocity[i] for i in cluster_indices_list]),
                azimuth=np.array([point_cloud.azimuth[i] for i in cluster_indices_list]),
                elevation=np.array([point_cloud.elevation[i] for i in cluster_indices_list]),
                rcs=np.array([point_cloud.rcs[i] for i in cluster_indices_list]),
                snr=np.array([point_cloud.snr[i] for i in cluster_indices_list])
            )
            
            # Create cluster object with metadata
            metadata = {
                'label': int(label),
                'density': float(density),  # Convert to scalar
                'avg_snr': mean_snr,
                'avg_rcs': mean_rcs,
                'volume': float(volume)
            }
            
            cluster = Cluster(
                points=cluster_points,
                centroid=centroid,
                velocity=mean_velocity,
                size=size,
                point_indices=cluster_indices,
                metadata=metadata
            )
            clusters.append(cluster)
            
        return clusters 