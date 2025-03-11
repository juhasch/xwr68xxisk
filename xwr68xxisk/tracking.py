"""Point cloud tracking module for radar data.

This module provides tracking functionality for radar point cloud clusters,
implementing a simple Kalman filter-based tracking system.
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from filterpy.kalman import KalmanFilter
from xwr68xxisk.clustering import Cluster


@dataclass
class Track:
    """Class representing a tracked object."""
    track_id: int
    cluster: Cluster
    state: np.ndarray  # [x, y, z, vx, vy, vz]
    covariance: np.ndarray
    age: int  # number of frames this track has existed
    hits: int  # number of frames with successful measurements
    misses: int  # number of frames without measurements
    metadata: Dict = None


class PointCloudTracker:
    """Class to perform tracking on radar point cloud clusters."""
    
    def __init__(self,
                 dt: float = 0.1,  # time step between frames
                 max_distance: float = 2.0,  # maximum distance for association
                 min_hits: int = 3,  # minimum hits before track is confirmed
                 max_misses: int = 5):  # maximum misses before track is dropped
        """
        Initialize tracker.
        
        Args:
            dt: Time step between frames (seconds)
            max_distance: Maximum distance for cluster-to-track association (meters)
            min_hits: Minimum hits before track is confirmed
            max_misses: Maximum misses before track is dropped
        """
        self.dt = dt
        self.max_distance = max_distance
        self.min_hits = min_hits
        self.max_misses = max_misses
        
        self.tracks: List[Track] = []
        self.next_track_id = 0
        
        # Initialize Kalman filter parameters
        self.F = np.array([  # State transition matrix
            [1, 0, 0, dt, 0, 0],  # x = x + vx*dt
            [0, 1, 0, 0, dt, 0],  # y = y + vy*dt
            [0, 0, 1, 0, 0, dt],  # z = z + vz*dt
            [0, 0, 0, 1, 0, 0],   # vx = vx
            [0, 0, 0, 0, 1, 0],   # vy = vy
            [0, 0, 0, 0, 0, 1]    # vz = vz
        ])
        
        self.H = np.array([  # Measurement matrix (we only measure position)
            [1, 0, 0, 0, 0, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 0, 1, 0, 0, 0]
        ])
        
        # Process noise (adjust these based on your radar's characteristics)
        self.Q = np.eye(6) * 0.1
        self.Q[3:, 3:] *= 0.2  # More uncertainty in velocity
        
        # Measurement noise (adjust based on your radar's characteristics)
        self.R = np.eye(3) * 0.1
        
    def _create_kalman_filter(self, cluster: Cluster) -> KalmanFilter:
        """Create and initialize a Kalman filter for a new track."""
        kf = KalmanFilter(dim_x=6, dim_z=3)
        kf.F = self.F
        kf.H = self.H
        kf.Q = self.Q
        kf.R = self.R
        
        # Initialize state with cluster centroid and estimated velocity
        kf.x = np.zeros(6)
        kf.x[:3] = cluster.centroid
        # Estimate initial velocity from cluster velocity (project onto x,y,z)
        # This is a simplification - could be improved with better velocity projection
        kf.x[3:] = cluster.velocity / np.sqrt(3)
        
        # Initialize covariance matrix
        kf.P = np.eye(6) * 1.0
        kf.P[3:, 3:] *= 2.0  # Higher uncertainty in velocity
        
        return kf
        
    def _associate_clusters(self, clusters: List[Cluster]) -> Tuple[Dict[int, int], List[int]]:
        """
        Associate clusters with existing tracks using simple nearest neighbor.
        
        Returns:
            Tuple containing:
                - Dictionary mapping track indices to cluster indices
                - List of unassigned cluster indices
        """
        if not self.tracks or not clusters:
            return {}, list(range(len(clusters)))
            
        # Calculate distance matrix
        cost_matrix = np.zeros((len(self.tracks), len(clusters)))
        for i, track in enumerate(self.tracks):
            for j, cluster in enumerate(clusters):
                cost_matrix[i, j] = np.linalg.norm(track.state[:3] - cluster.centroid)
                
        # Simple greedy association (could be improved with Hungarian algorithm)
        associations = {}
        used_clusters = set()
        
        for i in range(len(self.tracks)):
            min_dist = self.max_distance
            best_match = -1
            
            for j in range(len(clusters)):
                if j not in used_clusters and cost_matrix[i, j] < min_dist:
                    min_dist = cost_matrix[i, j]
                    best_match = j
                    
            if best_match >= 0:
                associations[i] = best_match
                used_clusters.add(best_match)
                
        # Get unassigned clusters
        unassigned = [j for j in range(len(clusters)) if j not in used_clusters]
        
        return associations, unassigned
        
    def update(self, clusters: List[Cluster]) -> List[Track]:
        """
        Update tracks with new cluster measurements.
        
        Args:
            clusters: List of new cluster measurements
            
        Returns:
            List of confirmed tracks
        """
        # Associate clusters with existing tracks
        associations, unassigned_clusters = self._associate_clusters(clusters)
        
        # Update tracks with associated clusters
        for track_idx, cluster_idx in associations.items():
            track = self.tracks[track_idx]
            cluster = clusters[cluster_idx]
            
            # Create Kalman filter if this is first hit
            if not hasattr(track, 'kf'):
                track.kf = self._create_kalman_filter(cluster)
            
            # Update Kalman filter with measurement
            track.kf.predict()
            track.kf.update(cluster.centroid)
            
            # Update track properties
            track.state = track.kf.x
            track.covariance = track.kf.P
            track.cluster = cluster
            track.hits += 1
            track.age += 1
            track.misses = 0
            
        # Update tracks without associations
        for i in range(len(self.tracks)):
            if i not in associations:
                track = self.tracks[i]
                if hasattr(track, 'kf'):
                    track.kf.predict()
                track.misses += 1
                track.age += 1
                
        # Create new tracks for unassigned clusters
        for cluster_idx in unassigned_clusters:
            cluster = clusters[cluster_idx]
            track = Track(
                track_id=self.next_track_id,
                cluster=cluster,
                state=np.zeros(6),  # Will be initialized with Kalman filter
                covariance=np.eye(6),
                age=1,
                hits=1,
                misses=0
            )
            track.kf = self._create_kalman_filter(cluster)
            track.state = track.kf.x
            track.covariance = track.kf.P
            
            self.tracks.append(track)
            self.next_track_id += 1
            
        # Remove dead tracks
        self.tracks = [track for track in self.tracks 
                      if track.misses <= self.max_misses]
        
        # Return only confirmed tracks
        confirmed_tracks = [track for track in self.tracks 
                          if track.hits >= self.min_hits]
        
        return confirmed_tracks 