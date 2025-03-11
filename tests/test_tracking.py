"""Tests for point cloud tracking functionality."""

import numpy as np
import pytest
from xwr68xxisk.point_cloud import RadarPointCloud
from xwr68xxisk.clustering import Cluster
from xwr68xxisk.tracking import PointCloudTracker, Track


def create_test_cluster(centroid, velocity=0.0, size=None, num_points=10):
    """Helper function to create a test cluster."""
    if size is None:
        size = np.array([0.5, 0.5, 0.5])
        
    # Create points around centroid
    points = np.random.normal(0, 0.1, (num_points, 3)) + centroid
    velocities = np.full(num_points, velocity)
    
    # Create point cloud
    ranges = np.sqrt(np.sum(points**2, axis=1))
    azimuths = np.arctan2(points[:, 0], points[:, 1])
    elevations = np.arcsin(points[:, 2] / ranges)
    
    point_cloud = RadarPointCloud(
        range=ranges,
        velocity=velocities,
        azimuth=azimuths,
        elevation=elevations,
        rcs=np.zeros(num_points),
        snr=np.zeros(num_points)
    )
    
    return Cluster(
        points=point_cloud,
        centroid=np.array(centroid),
        velocity=velocity,
        size=np.array(size),
        point_indices=np.arange(num_points),
        metadata={'label': 0}
    )


def test_tracker_initialization():
    """Test tracker initialization with different parameters."""
    tracker = PointCloudTracker(dt=0.1, max_distance=2.0, min_hits=3, max_misses=5)
    assert tracker.dt == 0.1
    assert tracker.max_distance == 2.0
    assert tracker.min_hits == 3
    assert tracker.max_misses == 5
    assert len(tracker.tracks) == 0


def test_single_stationary_target():
    """Test tracking of a single stationary target."""
    tracker = PointCloudTracker(dt=0.1)
    
    # Create a stationary cluster
    cluster = create_test_cluster([1.0, 1.0, 0.0])
    
    # Track for several frames
    tracks = []
    for _ in range(5):
        tracks = tracker.update([cluster])
        
    # After 3 frames (min_hits), should have one confirmed track
    assert len(tracks) == 1
    track = tracks[0]
    
    # Check track properties
    assert track.hits >= 3
    assert track.misses == 0
    assert np.allclose(track.state[:3], [1.0, 1.0, 0.0], atol=0.1)  # Position
    assert np.allclose(track.state[3:], [0.0, 0.0, 0.0], atol=0.1)  # Velocity


def test_single_moving_target():
    """Test tracking of a single moving target."""
    tracker = PointCloudTracker(dt=0.1)
    
    # Create clusters with moving centroid
    tracks_list = []
    for i in range(5):
        x = 1.0 + i * 0.1  # Moving in x direction at 1 m/s
        cluster = create_test_cluster([x, 1.0, 0.0], velocity=1.0)
        tracks_list.append(tracker.update([cluster]))
    
    # Get final tracks
    tracks = tracks_list[-1]
    assert len(tracks) == 1
    track = tracks[0]
    
    # Check estimated velocity
    assert track.state[3] > 0  # Should have positive x velocity
    assert np.isclose(track.state[3], 1.0, atol=0.3)  # Should be close to 1 m/s


def test_multiple_targets():
    """Test tracking of multiple targets."""
    tracker = PointCloudTracker(dt=0.1)
    
    # Create two clusters
    cluster1 = create_test_cluster([0.0, 0.0, 0.0])
    cluster2 = create_test_cluster([2.0, 2.0, 0.0])
    
    # Track for several frames
    tracks = []
    for _ in range(5):
        tracks = tracker.update([cluster1, cluster2])
    
    # Should have two confirmed tracks
    assert len(tracks) == 2
    
    # Tracks should be well-separated
    positions = np.array([t.state[:3] for t in tracks])
    distances = np.linalg.norm(positions[0] - positions[1])
    assert distances > 2.0


def test_track_deletion():
    """Test that tracks are deleted when missing for too long."""
    tracker = PointCloudTracker(dt=0.1, max_misses=2)
    
    # Create and track a cluster for a few frames
    cluster = create_test_cluster([1.0, 1.0, 0.0])
    for _ in range(5):
        tracks = tracker.update([cluster])
    assert len(tracks) == 1
    
    # Stop providing measurements
    for _ in range(3):
        tracks = tracker.update([])
    
    # Track should be deleted after max_misses frames
    assert len(tracks) == 0


def test_track_confirmation():
    """Test track confirmation process."""
    tracker = PointCloudTracker(dt=0.1, min_hits=3)
    
    # Create a cluster
    cluster = create_test_cluster([1.0, 1.0, 0.0])
    
    # First two updates should not produce confirmed tracks
    tracks1 = tracker.update([cluster])
    assert len(tracks1) == 0
    
    tracks2 = tracker.update([cluster])
    assert len(tracks2) == 0
    
    # Third update should confirm the track
    tracks3 = tracker.update([cluster])
    assert len(tracks3) == 1


def test_track_covariance():
    """Test track covariance estimation."""
    tracker = PointCloudTracker(dt=0.1)
    
    # Create a cluster with some noise
    cluster = create_test_cluster([1.0, 1.0, 0.0], num_points=20)
    
    # Track for several frames
    for _ in range(5):
        tracks = tracker.update([cluster])
    
    # Get final track
    track = tracks[0]
    
    # Covariance should be positive definite
    assert np.all(np.linalg.eigvals(track.covariance) > 0)
    
    # Position uncertainty should be smaller than velocity uncertainty
    pos_uncertainty = np.mean(np.diag(track.covariance)[:3])
    vel_uncertainty = np.mean(np.diag(track.covariance)[3:])
    assert pos_uncertainty < vel_uncertainty


def test_max_distance():
    """Test maximum association distance parameter."""
    tracker = PointCloudTracker(dt=0.1, max_distance=1.0)
    
    # Create initial cluster
    cluster1 = create_test_cluster([0.0, 0.0, 0.0])
    tracks = tracker.update([cluster1])
    
    # Create second cluster within max_distance
    cluster2 = create_test_cluster([0.5, 0.0, 0.0])
    tracks = tracker.update([cluster2])
    assert len(tracks) == 0  # Not confirmed yet
    
    # Create third cluster beyond max_distance
    cluster3 = create_test_cluster([2.0, 0.0, 0.0])
    tracks = tracker.update([cluster3])
    
    # Should create a new track instead of associating
    assert len(tracker.tracks) > 1


def test_empty_update():
    """Test tracker update with no clusters."""
    tracker = PointCloudTracker()
    
    # Create and track a cluster
    cluster = create_test_cluster([1.0, 1.0, 0.0])
    tracks = tracker.update([cluster])
    
    # Update with no clusters
    empty_tracks = tracker.update([])
    
    # Should maintain internal state but increment misses
    assert len(tracker.tracks) > 0
    assert tracker.tracks[0].misses > 0 