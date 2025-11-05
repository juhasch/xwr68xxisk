"""This modules contains many clustering algorithms, either using well-known python packages like
scikit-learn either implemented in-house. """
from functools import reduce
from abc import ABC, abstractmethod

import numpy as np
from scipy.spatial.distance import cdist
from sklearn.cluster import DBSCAN, OPTICS, KMeans
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster._dbscan_inner import dbscan_inner
from sklearn.mixture import GaussianMixture
from sklearn.base import BaseEstimator, ClusterMixin

from radar_baseband_processor.baseband.targets import Targets


class ClusterMaker(ABC):
    """Class responsible for finding clusters.

    Examples
    --------
    >>> _config_cluster = dict(METHOD='DBSCAN',
    >>>                        KWARGS=dict(centroid_method='weighted_average', min_targets=5,
    >>>                                    eps=1))
    >>> cluster_maker = ClusterMaker.create(_config_cluster)
    """
    def __init__(self, centroid_method: str):
        """Init Base class

        Parameters
        ----------
        centroid_method
            Method for extracting the center of the cluster
        """
        self.centroid_method = centroid_method

    @abstractmethod
    def do(self, targets: Targets):
        """Abstract method for running the clustering algorithm

        Parameters
        ----------
        targets
            Point-cloud with attributes of detected targets.

        Returns
        -------
        targets_cluster_label : np.ndarray (target)
            Array with label of cluster for each target
        """

    @staticmethod
    def create(cluster_config: dict):
        """Factory method

        Parameters
        ----------
        cluster_config
            Configuration of cluster"""
        method = cluster_config['METHOD']
        kwargs = cluster_config['KWARGS']
        if method == 'DBSCAN':
            obj = ClusterMakerDBSCAN(**kwargs)
        elif method == 'OPTICS':
            obj = ClusterMakerOPTICS(**kwargs)
        elif method == 'HDBSCAN':
            obj = ClusterMakerHDBSCAN(**kwargs)
        elif method == 'GridBasedDBSCAN':
            obj = ClusterMakerGridBasedDBSCAN(**kwargs)
        elif method == 'KMEANS':
            obj = ClusterMakerKMeans(**kwargs)
        elif method == 'GMM':
            obj = ClusterMakerGMM(**kwargs)
        else:
            raise ValueError('Unknown clustering method')
        return obj

    def calc_cluster_center(self, targets_cluster_label: np.ndarray, targets: Targets) -> Targets:
        """Calculate the center of the cluster.

        Parameters
        ----------
        targets_cluster_label
            Array with label of cluster for each target
        targets
            Detected targets

        Returns
        -------
        clusters
            Point-Cloud with clusters
        """
        if targets_cluster_label.size == 0:
            return None  # No targets detected
        unique_clusters = np.unique(targets_cluster_label)
        if 0 in unique_clusters:  # Clustering algorithm found at least one cluster
            n_unique_clusters = unique_clusters.size
            if -1 in unique_clusters:
                n_unique_clusters -= 1
            range_c = np.zeros(n_unique_clusters)
            angle_az_c = np.zeros(n_unique_clusters)
            radial_vel_c = np.zeros(n_unique_clusters)
            cnt_cluster = 0
            for cluster_id in unique_clusters:
                if cluster_id == -1:
                    continue
                idx_in_cluster = np.nonzero(targets_cluster_label == cluster_id)[0]
                range_t = targets.pos_spherical[idx_in_cluster, 0]
                angle_az_t = targets.pos_spherical[idx_in_cluster, 1]
                radial_vel_t = targets.radial_vel[idx_in_cluster]
                if self.centroid_method == 'median':
                    range_est = np.median(range_t)
                    azimuth_est = np.median(angle_az_t)
                    radial_vel_est = np.median(radial_vel_t)
                elif self.centroid_method == 'weighted_average':
                    # More info in http://ieeexplore.ieee.org/document/7850967/ page 6
                    amplitude_t = targets.magnitude[idx_in_cluster]
                    range_est = np.average(range_t, axis=None, weights=amplitude_t)
                    azimuth_est = np.average(angle_az_t, axis=None, weights=amplitude_t)
                    radial_vel_est = np.average(radial_vel_t, axis=None, weights=amplitude_t)
                else:
                    raise TypeError(f'Unknown Centroid method {self.centroid_method}')
                range_c[cnt_cluster] = float(range_est)
                angle_az_c[cnt_cluster] = float(azimuth_est)
                radial_vel_c[cnt_cluster] = float(radial_vel_est)
                cnt_cluster += 1
            clusters = Targets.create(range=range_c, radial_vel=radial_vel_c,
                                      aoa_az=-angle_az_c+np.pi/2,
                                      aoa_el=np.full_like(angle_az_c, 0))
        else:
            clusters = None  # Clustering algorithm did not find clusters
        return clusters

####################################################
# Cluster Algorithms from Scikit-Learn
####################################################


class ClusterMakerDBSCAN(ClusterMaker):
    """Concrete class that implements the DBSCAN algorithm using scikit-learn"""
    def __init__(self, centroid_method: str, min_targets: int, eps: float, n_jobs: int = None,
                 **kwargs):
        """Initialization of ClusterMakerDBSCAN

        Parameters
        ----------
        min_targets
            Minimum number of targets for each cluster
        eps
            Radius of cluster
        """
        super().__init__(centroid_method)
        self.min_targets = min_targets
        self.algorithm = DBSCAN(eps=eps, min_samples=min_targets, metric='precomputed',
                                n_jobs=n_jobs)

    def do(self, targets: Targets):
        targets_pos = targets.pos_cartesian
        distance = cdist(targets_pos, targets_pos)
        targets_cluster_label = self.algorithm.fit_predict(distance)
        return targets_cluster_label


class ClusterMakerOPTICS(ClusterMaker):
    """Concrete class that implements the OPTICS algorithm using scikit-learn"""
    def __init__(self, centroid_method: str, min_targets: int, xi: float = 0.05,
                 n_jobs: int = None, **kwargs):
        """

        Parameters
        ----------
        min_targets
            Minimum number of targets for each cluster
        xi
        n_jobs
        """
        super().__init__(centroid_method)
        self.min_targets = min_targets
        self.algorithm = OPTICS(min_samples=min_targets, xi=xi, n_jobs=n_jobs)

    def do(self, targets: Targets):
        targets_pos = targets.pos_cartesian
        targets_cluster_label = self.algorithm.fit_predict(targets_pos)
        return targets_cluster_label


class ClusterMakerKMeans(ClusterMaker):
    """Concrete class that implements the K-means algorithm using scikit-learn"""
    def __init__(self, centroid_method: str, n_clusters: float, **kwargs):
        """

        Parameters
        ----------
        n_clusters
            Number of clusters
        """
        super().__init__(centroid_method)
        self.n_clusters = n_clusters
        self.algorithm = KMeans(n_clusters=n_clusters)

    def do(self, targets: Targets):
        targets_pos = targets.pos_cartesian
        targets_cluster_label = self.algorithm.fit_predict(targets_pos)
        return targets_cluster_label


class ClusterMakerGMM(ClusterMaker):
    """Concrete class that implements the Gaussian Mixture Model using scikit-learn"""
    def __init__(self, centroid_method: str, n_clusters: float):
        """

        Parameters
        ----------
        n_clusters
            Number of clusters
        """
        super().__init__(centroid_method)
        self.n_clusters = n_clusters
        self.algorithm = GaussianMixture(n_components=n_clusters)

    def do(self, targets: Targets):
        targets_pos = targets.pos_cartesian
        targets_cluster_label = self.algorithm.fit_predict(targets_pos)
        return targets_cluster_label

####################################################
# Cluster Algorithms from 3rt parties
####################################################


class ClusterMakerHDBSCAN(ClusterMaker):
    """Concrete class that implements the HDBSCAN algorithm. More info in:
     https://hdbscan.readthedocs.io/en/latest/index.html"""
    def __init__(self, centroid_method: str, min_targets: int):
        """Initialization of ClusterMakerHDBSCAN
        """
        super().__init__(centroid_method)
        self.min_targets = min_targets
        import hdbscan
        self.algorithm = hdbscan.HDBSCAN(min_cluster_size=min_targets)

    def do(self, targets: Targets):
        targets_pos = targets.pos_cartesian
        targets_cluster_label = self.algorithm.fit_predict(targets_pos)
        return targets_cluster_label


####################################################
# Cluster Algorithms from Bosch
####################################################


class ClusterMakerGridBasedDBSCAN(ClusterMaker):
    """Concrete class that implements the grid-based DBSCAN algorithm using scikit-learn"""
    def __init__(self, centroid_method: str, eps: list, min_targets: int, ):
        """Initialization

        Parameters
        ----------
        eps
            Radius of cluster
        """
        super().__init__(centroid_method)
        self.min_targets = min_targets
        self.algorithm = GridBasedDBSCAN(eps, min_targets)

    def do(self, targets: Targets):
        X = np.vstack([targets.fast_time, targets.aoa_ind_az]).T
        targets_cluster_label = self.algorithm.fit_predict(X)
        return targets_cluster_label


class GridBasedDBSCAN(ClusterMixin, BaseEstimator):
    """"""

    def __init__(self, eps: list, min_samples: int, algorithm: str = 'auto',
                 n_jobs: float = -1):
        self.eps = eps
        self.n_features = len(eps)
        self.min_samples = min_samples
        self.algorithm = algorithm
        self.n_jobs = n_jobs
        self.metric = 'precomputed'
        self.neighbors_models = []
        self.labels_ = None
        for idx_feature in range(self.n_features):
            neighbors_model = NearestNeighbors(radius=self.eps, algorithm=self.algorithm,
                                               metric=self.metric, n_jobs=self.n_jobs)
            self.neighbors_models.append(neighbors_model)

    def fit(self, X: np.ndarray, y=None, sample_weight=None):
        """Perform grid-based DBSCAN clustering from features, or distance matrix.

        Parameters
        ----------
        X : (n_samples, n_features)
            Distances between instances
        sample_weight:
            Not used, present here for API consistency by convention.
        y :
            Not used, present here for API consistency by convention.
        """
        if X.shape[1] != self.n_features:
            raise ValueError(f'Wrong number of features {X.shape[1]}')
        n_samples = X.shape[0]
        neigh_ind_l = []
        # Find neighbors that satisfy the distance criterion provided by the user, for each
        # feature
        for idx_feature in range(self.n_features):
            distance_feature = cdist(X[:, [idx_feature]], X[:, [idx_feature]], 'minkowski', p=1.)
            neighbors_model = self.neighbors_models[idx_feature]
            neighbors_model.fit(distance_feature)
            neigh_ind = neighbors_model.radius_neighbors(distance_feature,
                                                         radius=self.eps[idx_feature],
                                                         return_distance=False)
            neigh_ind_l.append(neigh_ind)

        # Find neighborhoods that satisfy the above criteria, similar to DBSCAN for euclidean
        # distance
        n_neighbors = np.zeros(n_samples, dtype=int)
        neighborhoods_l = []
        for idx_sample in range(n_samples):
            arrays_l = []
            for idx_feature in range(self.n_features):
                arrays_l.append(neigh_ind_l[idx_feature][idx_sample])
            neighbors = reduce(np.intersect1d, arrays_l)
            n_neighbors[idx_sample] = neighbors.size
            neighborhoods_l.append(neighbors)
        neighborhoods = np.array(neighborhoods_l, dtype=object)

        labels = np.full(n_samples, -1, dtype=np.intp)  # Initially, all samples are noise.

        # A list of all core samples found.
        core_samples = np.asarray(n_neighbors >= self.min_samples, dtype=np.uint8)
        try:
            dbscan_inner(core_samples, neighborhoods, labels)
        except:
            # All core_samples are true
            labels = labels * 0
        self.labels_ = labels
