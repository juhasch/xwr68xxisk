"""Tests for point cloud clustering functionality."""

import numpy as np
import pytest
from xwr68xxisk.point_cloud import RadarPointCloud
from xwr68xxisk.clustering import PointCloudClustering, Cluster


def create_test_point_cloud(points_xyz, velocities=None):
    """Helper function to create a test point cloud."""
    points = np.array(points_xyz)
    n_points = len(points)
    
    if n_points == 0:
        return RadarPointCloud(
            range=np.array([]),
            velocity=np.array([]),
            azimuth=np.array([]),
            elevation=np.array([]),
            rcs=np.array([]),
            snr=np.array([])
        )
    
    # Convert Cartesian to spherical coordinates
    ranges = np.sqrt(np.sum(points**2, axis=1))
    # Handle points at origin separately
    origin_mask = ranges == 0
    ranges[origin_mask] = 1e-10  # Small non-zero value
    
    # Calculate angles
    azimuths = np.arctan2(points[:, 1], points[:, 0])  # Swapped x and y for correct azimuth
    elevations = np.arcsin(np.clip(points[:, 2] / ranges, -1, 1))
    
    if velocities is None:
        velocities = np.zeros(n_points)
    
    return RadarPointCloud(
        range=ranges,
        velocity=velocities,
        azimuth=azimuths,
        elevation=elevations,
        rcs=np.zeros(n_points),
        snr=np.zeros(n_points)
    )


def test_empty_point_cloud():
    """Test clustering with empty point cloud."""
    clusterer = PointCloudClustering(eps=0.5, min_samples=2)
    point_cloud = create_test_point_cloud([])
    clusters = clusterer.cluster(point_cloud)
    assert len(clusters) == 0


def test_single_cluster():
    """Test clustering with points that should form a single cluster."""
    points = [
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0],
        [0.1, 0.1, 0]
    ]
    point_cloud = create_test_point_cloud(points)
    
    clusterer = PointCloudClustering(eps=0.2, min_samples=2)
    clusters = clusterer.cluster(point_cloud)
    
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.num_points == 4
    assert np.allclose(cluster.centroid, [0.05, 0.05, 0])
    assert np.allclose(cluster.size, [0.1, 0.1, 0])


def test_multiple_clusters():
    """Test clustering with points that should form multiple clusters."""
    points = [
        # Cluster 1
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0],
        # Cluster 2
        [1, 1, 0],
        [1.1, 1, 0],
        [1, 1.1, 0],
        # Noise point
        [2, 2, 0]
    ]
    point_cloud = create_test_point_cloud(points)
    
    clusterer = PointCloudClustering(eps=0.2, min_samples=2)
    clusters = clusterer.cluster(point_cloud)
    
    assert len(clusters) == 2
    
    # Clusters should be sorted by size/position, so we can check them in order
    assert clusters[0].num_points == 3
    assert clusters[1].num_points == 3
    
    # Check first cluster centroid (approximately)
    assert np.allclose(clusters[0].centroid, [0.033, 0.033, 0], atol=0.1)
    
    # Check second cluster centroid (approximately)
    assert np.allclose(clusters[1].centroid, [1.033, 1.033, 0], atol=0.1)


def test_velocity_clustering():
    """Test clustering with velocity information."""
    points = [
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0]
    ]
    velocities = [1.0, 1.1, 0.9]  # Similar velocities
    point_cloud = create_test_point_cloud(points, velocities)
    
    clusterer = PointCloudClustering(eps=0.2, min_samples=2)
    clusters = clusterer.cluster(point_cloud)
    
    assert len(clusters) == 1
    cluster = clusters[0]
    assert np.isclose(cluster.velocity, 1.0, atol=0.1)


def test_cluster_metadata():
    """Test cluster metadata and properties."""
    points = [
        [0, 0, 0],
        [0.1, 0, 0],
        [0, 0.1, 0]
    ]
    point_cloud = create_test_point_cloud(points)
    
    clusterer = PointCloudClustering(eps=0.2, min_samples=2)
    clusters = clusterer.cluster(point_cloud)
    
    assert len(clusters) == 1
    cluster = clusters[0]
    
    # Check metadata
    assert isinstance(cluster.metadata, dict)
    assert 'label' in cluster.metadata
    assert 'density' in cluster.metadata
    assert cluster.metadata['density'] > 0


def test_clustering_parameters():
    """Test different clustering parameters."""
    points = [
        [0, 0, 0],
        [0.1, 0, 0],
        [0.2, 0, 0],
        [1, 0, 0],
        [1.1, 0, 0]
    ]
    point_cloud = create_test_point_cloud(points)
    
    # With small eps, should get more clusters
    clusterer_small = PointCloudClustering(eps=0.12, min_samples=2)
    clusters_small = clusterer_small.cluster(point_cloud)
    
    # With large eps, should get fewer clusters
    clusterer_large = PointCloudClustering(eps=1.5, min_samples=2)
    clusters_large = clusterer_large.cluster(point_cloud)
    
    assert len(clusters_small) > len(clusters_large)


def test_invalid_algorithm():
    """Test that invalid clustering algorithm raises error."""
    with pytest.raises(ValueError):
        PointCloudClustering(algorithm='invalid')


def test_min_samples():
    """Test minimum samples parameter."""
    points = [
        [0, 0, 0],
        [0.1, 0, 0],
        [0.2, 0, 0]
    ]
    point_cloud = create_test_point_cloud(points)
    
    # Should form one cluster with min_samples=2
    clusterer_2 = PointCloudClustering(eps=0.3, min_samples=2)
    clusters_2 = clusterer_2.cluster(point_cloud)
    
    # Should form no clusters with min_samples=4
    clusterer_4 = PointCloudClustering(eps=0.3, min_samples=4)
    clusters_4 = clusterer_4.cluster(point_cloud)
    
    assert len(clusters_2) == 1
    assert len(clusters_4) == 0 