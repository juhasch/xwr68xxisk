"""Contains Filters used for Parameter Estimation"""
import numpy as np
from numpy.random import random
import scipy.stats
from filterpy.monte_carlo.resampling import residual_resample, stratified_resample, \
    systematic_resample, multinomial_resample


class ParticleFilter:
    def __init__(self, dim_x: int, dt: float, fx: callable, hx: callable, n_particles: int,
                 init_state: np.ndarray, init_var: np.ndarray, resampling_method: str):
        """

        Parameters
        ----------
        dim_x
            Dimensions of the state
        dt : float
            Time between steps in seconds.
        fx : function(x,dt)
            function that returns the state x transformed by the
            state transition function. dt is the time step in seconds.
        hx : function(x)
            Measurement function. Converts state vector x into a measurement
            vector of shape (dim_z).
        n_particles
            Number of particles
        init_state
            Initial guess of the state
        init_var
            Variance of initial state
        resampling_method
            Resampling method
        """
        self.n_particles = n_particles
        self.x = init_state
        self._init_var = init_var
        self.var = init_var
        self.weights = np.full(n_particles, 1 / n_particles)
        self._dim_x = dim_x
        self._dt = dt
        self._fx = fx
        self._hx = hx
        self.gen = np.random.default_rng(0)
        self.particles = self.create_particles_gaussian(self.x, self.var)
        self.random_variable = scipy.stats.norm(0, 0.2)
        if resampling_method == 'residual_resample':
            self.resampling_fun = residual_resample
        elif resampling_method == 'stratified_resample':
            self.resampling_fun = stratified_resample
        elif resampling_method == 'systematic_resample':
            self.resampling_fun = systematic_resample
        elif resampling_method == 'multinomial_resample':
            self.resampling_fun = multinomial_resample
        else:
            raise ValueError(f'Unknown resampling method {resampling_method}')

    def predict(self, u=0):
        """Predict step of the filter. Adding noise is very important for the resampling part"""
        process_noise = np.zeros_like(self.particles)
        _std = np.sqrt(self._init_var)
        for idx_dim in range(self._dim_x):
            process_noise[:, idx_dim] = self.gen.normal(0, _std[idx_dim], self.n_particles)
        self.particles = self._fx(self.particles.T, self._dt).T + process_noise

    def update(self, observation: np.ndarray = None):
        """Update step of the filter"""
        if observation is not None:
            observation_pred = self._hx(self.particles.T).T
            # simplification assumes variance is invariant to world projection
            # TODO: use multiple random variables from multiple sensors (range, angle, velocity)?
            dist = np.linalg.norm(observation_pred - observation, axis=-1)
            prob = self.random_variable.pdf(dist)

            # particles far from a measurement will give us 0.0 for a probability
            # due to floating point limits. Once we hit zero we can never recover,
            # so add some small nonzero value to all points.
            self.weights *= prob + 1e-12
            self.weights /= sum(self.weights)  # normalize

            # Resample
            # resample if too few effective particles
            # TODO: make the threshold configurable
            threshold = self.n_particles / 2
            if self.n_effective_particles < threshold:
                indexes = self.resampling_fun(self.weights)
                self.resample_from_index(self.particles, self.weights, indexes)

            # Estimate new state
            self.x = np.average(self.particles, weights=self.weights, axis=0)
            self.var = np.average((self.particles - self.x) ** 2, weights=self.weights, axis=0)

    @property
    def n_effective_particles(self):
        """Number of effective particles, approximately measures the number of particles which
        meaningfully contribute to the probability distribution"""
        return 1. / np.sum(np.square(self.weights))

    @staticmethod
    def resample_from_index(particles, weights, indexes):
        particles[:] = particles[indexes]
        weights.resize(len(particles))
        weights.fill(1.0 / len(weights))

    def create_particles_gaussian(self, mean, std):
        state_len = mean.size
        particles = np.empty((self.n_particles, state_len))
        for idx_state in range(state_len):
            particles[:, idx_state] = \
                self.gen.normal(mean[idx_state], std[idx_state], self.n_particles)
        return particles


class MMVelEst:
    """Multiple Model Velocity Estimation"""
    def __init__(self, filters: list, accuracy_threshold: float):
        """

        Parameters
        ----------
        filters
            List of N filters. filters[i] is the ith Kalman filter.
        accuracy_threshold
        """
        self.accuracy_threshold = accuracy_threshold
        self.filters = filters
        self.x = self.filters[0].x
        self.P = self.filters[0].P

        # Initialize state estimate based on current filters
        self.x_prior = self.x.copy()
        self.P_prior = self.P.copy()
        self.x_post = self.x.copy()
        self.P_post = self.P.copy()

    def predict(self, u=None):
        """Predict next state (prior) using the IMM state propagation
        equations.

        Parameters
        ----------

        u : np.array, optional
            Control vector. If not `None`, it is multiplied by B
            to create the control input into the system.
        """
        for _filter in self.filters:
            _filter.x = self.x.copy()
            _filter.P = self.P.copy()
            _filter.predict(u)

    def update(self, z_augmented: np.ndarray = None):
        """Add a new measurement (z) to the filter. If z is None, nothing
        is changed.

        Parameters
        ----------
        z_augmented
            Measurement vector for this update. Last element is the accuracy of vel estimation
        """

        if z_augmented is None:
            _filter = self.filters[0]
            z = z_augmented
        else:
            accuracy = z_augmented[-1]
            z = z_augmented[:-1]
            if 0 < accuracy < self.accuracy_threshold:
                # Use velocity values
                _filter = self.filters[1]
            else:
                z = z[:2]
                _filter = self.filters[0]
        _filter.update(z)
        self.x = _filter.x.copy()
        self.P = _filter.P.copy()
        self.x_post = self.x.copy()
        self.P_post = self.P.copy()

