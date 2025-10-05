"""
Plot manager for radar visualization.

This module provides a PlotManager class that manages multiple visualization tabs
for radar data, including scatter plots and range profiles.
"""

import logging
from collections import deque
import numpy as np
import panel as pn
import holoviews as hv
import param
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, ColorBar, LinearColorMapper, Range1d
from bokeh.layouts import column
from bokeh.palettes import Viridis256
from bokeh.transform import linear_cmap
from scipy.signal import find_peaks
from ..radar_config_models import RadarConfig
from ..parse import RadarData

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize extensions
hv.extension('bokeh')
pn.extension(design="material", sizing_mode="stretch_width")


class BasePlot(param.Parameterized):
    """Base class for all plot types."""
    
    def __init__(self, scene_config: RadarConfig, display_config: 'DisplayConfig'):
        """Initialize the base plot.
        
        Args:
            scene_config: The scene profile configuration
            display_config: The display configuration
        """
        super().__init__()
        self.scene_config = scene_config
        self.display_config = display_config
        self.plot = self._setup_plot()
        
    def _setup_plot(self) -> pn.pane.Bokeh:
        """Set up the plot. To be implemented by subclasses."""
        raise NotImplementedError
        
    def update(self, radar_data: RadarData) -> None:
        """Update the plot with new radar data. To be implemented by subclasses."""
        raise NotImplementedError
        
    @property
    def view(self) -> pn.pane.Bokeh:
        """Get the Panel plot view."""
        return self.plot


class ScatterPlot(BasePlot):
    """Scatter plot for radar point cloud visualization."""
    
    def _setup_plot(self) -> pn.pane.Bokeh:
        """Set up the scatter plot."""
        p = figure(
            title='Radar Point Cloud',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            x_range=self.display_config.x_range,
            y_range=self.display_config.y_range,
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above'
        )
        
        self.data_source = ColumnDataSource({
            'x': [], 
            'y': [], 
            'velocity': [], 
            'size': []
        })
        
        self.color_mapper = LinearColorMapper(palette='Viridis256', low=-1, high=1)
        
        self.scatter_source = p.scatter(
            x='x',
            y='y', 
            size='size',
            fill_color={'field': 'velocity', 'transform': self.color_mapper},
            line_color=None,
            alpha=0.6,
            source=self.data_source,
            name='point_cloud'
        )
        
        color_bar = ColorBar(
            color_mapper=self.color_mapper,
            title='Velocity (m/s)',
            location=(0, 0)
        )
        p.add_layout(color_bar, 'right')
        
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'normal'
        p.xaxis.axis_label = 'X Position (m)'
        p.yaxis.axis_label = 'Y Position (m)'
        
        p.grid.grid_line_alpha = 0.3
        
        return pn.pane.Bokeh(p)
    
    def update(self, radar_data: RadarData) -> None:
        """Update the scatter plot with new radar data."""
        if not radar_data:
            return
            
        try:
            point_cloud = radar_data.to_point_cloud()
            
            if point_cloud.num_points == 0:
                self.data_source.data = {'x': [], 'y': [], 'velocity': [], 'size': []}
                return
                
            x, y, z = point_cloud.to_cartesian()
            
            x_range = self.display_config.x_range
            y_range = self.display_config.y_range
            x = np.clip(x, x_range[0], x_range[1])
            y = np.clip(y, y_range[0], y_range[1])
            
            velocity = point_cloud.velocity * 0.2  # Scale velocity for better visualization
            velocity = np.clip(velocity, -1, 1)
            
            if hasattr(point_cloud, 'snr') and point_cloud.snr is not None and len(point_cloud.snr) > 0:
                snr_values = point_cloud.snr
            else:
                snr_values = np.ones(point_cloud.num_points) * 30
                
            point_sizes = 5 + np.clip(snr_values / 60.0, 0, 1) * 15
            
            min_length = min(len(x), len(y), len(velocity), len(point_sizes))
            
            self.data_source.data = {
                'x': x[:min_length],
                'y': y[:min_length],
                'velocity': velocity[:min_length],
                'size': point_sizes[:min_length]
            }
            
        except Exception as e:
            logger.error(f"Error updating scatter plot: {e}")
            self.data_source.data = {'x': [], 'y': [], 'velocity': [], 'size': []}


class RangeProfilePlot(BasePlot):
    """Range profile plot showing signal strength vs range."""
    
    def _setup_plot(self) -> pn.pane.Bokeh:
        """Set up the range profile plot."""
        p = figure(
            title='Range Profile (Log Magnitude) & Noise Floor',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            y_range=(0, 90),  # Fixed y-axis range from 0 to +90 dB
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above'
        )
        
        self.range_data_source = ColumnDataSource({
            'range': [],
            'magnitude': []
        })
        
        self.noise_data_source = ColumnDataSource({
            'range': [],
            'noise': []
        })
        
        # Complex range profile data sources
        self.complex_magnitude_source = ColumnDataSource({
            'range': [],
            'magnitude': []
        })
        
        self.complex_phase_source = ColumnDataSource({
            'range': [],
            'phase': []
        })
        
        # Range profile line (blue) - used for both regular and complex log magnitude
        self.range_line = p.line(
            x='range',
            y='magnitude',
            line_width=2,
            color='blue',
            source=self.range_data_source,
            name='range_profile'
        )
        
        # Complex magnitude line (green) - not used anymore
        self.complex_magnitude_line = p.line(
            x='range',
            y='magnitude',
            line_width=2,
            color='green',
            source=self.complex_magnitude_source,
            name='complex_magnitude',
            visible=False
        )
        
        # Complex phase line (orange) - not used anymore
        self.complex_phase_line = p.line(
            x='range',
            y='phase',
            line_width=2,
            color='orange',
            source=self.complex_phase_source,
            name='complex_phase',
            visible=False
        )
        
        # Noise profile line (red)
        self.noise_line = p.line(
            x='range',
            y='noise',
            line_width=2,
            color='red',
            source=self.noise_data_source,
            name='noise_profile'
        )
        
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'normal'
        p.xaxis.axis_label = 'Range (m)'
        p.yaxis.axis_label = 'Magnitude (dB) / Phase (rad)'
        
        p.grid.grid_line_alpha = 0.3
        
        return pn.pane.Bokeh(p)
    
    def update(self, radar_data: RadarData) -> None:
        """Update the range profile plot with new radar data."""
        if not radar_data:
            logger.debug("RangeProfilePlot.update: radar_data is None or empty")
            return
            
        try:
            # Check what data is available
            has_complex_data = (radar_data.adc_complex is not None and 
                              len(radar_data.adc_complex) > 0)
            has_regular_data = (radar_data.adc is not None and 
                              len(radar_data.adc) > 0)
            has_noise_data = (radar_data.noise_profile is not None and 
                            len(radar_data.noise_profile) > 0)
            
            # Determine which data to show based on configuration and availability
            show_complex = (hasattr(self.scene_config, 'range_profile_mode') and 
                           self.scene_config.range_profile_mode == 'complex' and 
                           has_complex_data)
            
            # Update visibility based on available data and configuration
            self.range_line.visible = has_regular_data or (show_complex and has_complex_data)
            self.complex_magnitude_line.visible = False  # Not used anymore
            self.complex_phase_line.visible = False      # Not used anymore
            self.noise_line.visible = has_noise_data
            
            # Update range profile data
            if show_complex and has_complex_data:
                # Use complex range profile data - plot log magnitude (with averaging)
                range_bins, magnitude_dB, phase = radar_data.get_complex_range_profile()
                
                if len(range_bins) > 0 and len(magnitude_dB) > 0:
                    range_axis = self._get_range_axis(radar_data, len(range_bins))
                    
                    if len(range_axis) > 0:
                        min_len = min(len(magnitude_dB), len(range_axis))
                        self.range_data_source.data = {
                            'range': range_axis[:min_len],
                            'magnitude': magnitude_dB[:min_len]
                        }
                    else:
                        self.range_data_source.data = {'range': [], 'magnitude': []}
                else:
                    self.range_data_source.data = {'range': [], 'magnitude': []}
                    
            elif has_regular_data:
                # Use regular range profile data (sensor provides log magnitude in 0.1 dB units)
                magnitude_db = radar_data.adc.astype(np.float32) / 100.0
                range_axis = self._get_range_axis(radar_data, len(magnitude_db))
                
                if len(range_axis) > 0 and len(magnitude_db) > 0:
                    min_len = min(len(magnitude_db), len(range_axis))
                    self.range_data_source.data = {
                        'range': range_axis[:min_len],
                        'magnitude': magnitude_db[:min_len]
                    }
                else:
                    self.range_data_source.data = {'range': [], 'magnitude': []}
            else:
                self.range_data_source.data = {'range': [], 'magnitude': []}
            
            # Update noise profile data
            if has_noise_data:
                range_bins, noise_dB = radar_data.get_noise_profile()
                
                if len(range_bins) > 0 and len(noise_dB) > 0:
                    range_axis = self._get_range_axis(radar_data, len(range_bins))
                    
                    if len(range_axis) > 0:
                        min_len = min(len(noise_dB), len(range_axis))
                        self.noise_data_source.data = {
                            'range': range_axis[:min_len],
                            'noise': noise_dB[:min_len]
                        }
                    else:
                        self.noise_data_source.data = {'range': [], 'noise': []}
                else:
                    self.noise_data_source.data = {'range': [], 'noise': []}
            else:
                self.noise_data_source.data = {'range': [], 'noise': []}
                
        except Exception as e:
            logger.error(f"Error updating range profile plot: {e}")
            self.range_data_source.data = {'range': [], 'magnitude': []}
            self.noise_data_source.data = {'range': [], 'noise': []}
    
    def _get_range_axis(self, radar_data: RadarData, data_length: int) -> np.ndarray:
        """Get range axis for plotting."""
        if radar_data.config_params:
            range_step = radar_data.config_params.get('rangeStep')
            if range_step is not None:
                return np.arange(data_length) * range_step
            else:
                logger.warning("rangeStep not in radar_data.config_params. Cannot compute range axis.")
        else:
            logger.warning("radar_data.config_params is None or empty. Cannot compute range axis.")
        
        return np.array([])


class RangeWaterfallPlot(BasePlot):
    """Waterfall visualization for range profile history with fixed axes."""

    def __init__(self, scene_config: RadarConfig, display_config: 'DisplayConfig'):
        self.max_history = 200
        self.history = deque(maxlen=self.max_history)
        self.range_axis = np.array([])
        self.num_bins = 0
        self.range_step = 1.0
        self.time_step: float | None = None
        self.x_start = 0.0
        self.x_end = 1.0
        self.subtract_average = bool(getattr(display_config, 'waterfall_subtract_average', False))
        window_cfg = getattr(display_config, 'waterfall_average_window', 30)
        try:
            window_value = int(window_cfg)
        except (TypeError, ValueError):
            window_value = 30
        if window_value < 1:
            window_value = 1
        self.average_window = window_value
        self.baseline_buffer = deque(maxlen=min(self.average_window, self.max_history))
        self._figure = None
        self.image_source: ColumnDataSource | None = None
        self.color_mapper: LinearColorMapper | None = None
        self.color_bar: ColorBar | None = None
        super().__init__(scene_config, display_config)

    def _setup_plot(self) -> pn.pane.Bokeh:
        """Set up the range waterfall plot."""
        p = figure(
            title='Range Profile Waterfall',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            x_axis_label='Range (m)',
            y_axis_label='Time (s)',
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above',
            x_range=Range1d(self.x_start, self.x_end),
            y_range=Range1d(0, self.max_history)
        )

        self.color_mapper = LinearColorMapper(palette=Viridis256, low=0.0, high=1.0, nan_color='rgba(0,0,0,0)')
        initial_image = np.full((self.max_history, 1), np.nan, dtype=np.float32)
        self.image_source = ColumnDataSource({
            'image': [initial_image],
            'x': [self.x_start],
            'y': [0.0],
            'dw': [self.x_end - self.x_start],
            'dh': [self.max_history]
        })

        p.image(
            image='image',
            x='x',
            y='y',
            dw='dw',
            dh='dh',
            source=self.image_source,
            color_mapper=self.color_mapper,
            name='range_waterfall'
        )

        self.color_bar = ColorBar(
            color_mapper=self.color_mapper,
            title='Magnitude (dB)',
            location=(0, 0)
        )
        p.add_layout(self.color_bar, 'right')

        p.grid.grid_line_alpha = 0.3
        self._figure = p
        return pn.pane.Bokeh(p)

    def update(self, radar_data: RadarData) -> None:
        """Update the range waterfall plot with new radar data."""
        if not radar_data:
            logger.debug("RangeWaterfallPlot.update: radar_data is None or empty")
            self._clear_plot()
            return

        try:
            amplitude_db, range_axis = self._extract_range_profile(radar_data)

            if amplitude_db.size == 0 or range_axis.size == 0:
                logger.debug("RangeWaterfallPlot: No valid range profile data available")
                self._clear_plot()
                return

            if (self.num_bins == 0 or
                len(range_axis) != self.num_bins or
                not np.allclose(range_axis, self.range_axis)):
                self._initialize_axes(range_axis, radar_data)

            if self.num_bins == 0:
                return

            amplitude_trimmed = amplitude_db.astype(np.float32)
            if amplitude_trimmed.size > self.num_bins:
                amplitude_trimmed = amplitude_trimmed[:self.num_bins]
            elif amplitude_trimmed.size < self.num_bins:
                padded = np.full(self.num_bins, np.nan, dtype=np.float32)
                padded[:amplitude_trimmed.size] = amplitude_trimmed
                amplitude_trimmed = padded

            self._refresh_config_settings()

            baseline = self._compute_baseline() if self.subtract_average else None
            display_vector = amplitude_trimmed - baseline if baseline is not None else amplitude_trimmed

            self.history.append(display_vector)
            self._append_baseline(amplitude_trimmed)

            candidate_time_step = self._get_time_step(radar_data)
            if candidate_time_step > 0 and self.time_step is None:
                self.time_step = candidate_time_step
                self._update_time_axis()

            data_matrix = self._assemble_history_matrix()
            time_span = self._get_time_span()

            if self.image_source is not None:
                self.image_source.data = {
                    'image': [data_matrix],
                    'x': [self.x_start],
                    'y': [0.0],
                    'dw': [self.x_end - self.x_start],
                    'dh': [time_span]
                }

            if self._figure is not None:
                self._figure.x_range.start = self.x_start
                self._figure.x_range.end = self.x_end
                self._figure.y_range.start = 0.0
                self._figure.y_range.end = time_span

            if self.color_mapper is not None:
                valid_data = data_matrix[np.isfinite(data_matrix)]
                if valid_data.size == 0:
                    vmin, vmax = 0.0, 1.0
                else:
                    vmin = float(valid_data.min())
                    vmax = float(valid_data.max())
                    if vmin == vmax:
                        vmax = vmin + 1.0
                self.color_mapper.low = vmin
                self.color_mapper.high = vmax

        except Exception as e:
            logger.error(f"Error updating range waterfall plot: {e}")
            self._clear_plot()

    def _initialize_axes(self, range_axis: np.ndarray, radar_data: RadarData) -> None:
        """Initialize or reset axis metadata based on the incoming range axis."""
        if range_axis.size == 0:
            return

        self.range_axis = range_axis.astype(np.float32)
        self.num_bins = len(self.range_axis)
        self.history = deque(maxlen=self.max_history)
        self._reset_baseline()

        step = self._get_range_step(radar_data)
        if step <= 0 and self.num_bins > 1:
            step = float(self.range_axis[1] - self.range_axis[0])
        if step <= 0:
            step = 1.0
        self.range_step = step

        self.x_start = float(self.range_axis[0])
        self.x_end = self.x_start + self.range_step * max(self.num_bins, 1)
        if self.x_end <= self.x_start:
            self.x_end = self.x_start + self.range_step

        if self._figure is not None:
            self._figure.x_range.start = self.x_start
            self._figure.x_range.end = self.x_end

        self._refresh_empty_image()

    def _refresh_config_settings(self) -> None:
        """Pick up any runtime changes to waterfall configuration."""
        subtract_cfg = bool(getattr(self.display_config, 'waterfall_subtract_average', self.subtract_average))
        window_cfg = getattr(self.display_config, 'waterfall_average_window', self.average_window)

        try:
            window_value = int(window_cfg)
        except (TypeError, ValueError):
            window_value = self.average_window

        if window_value < 1:
            window_value = 1

        if window_value != self.average_window:
            self.average_window = window_value
            self._reset_baseline()

        if subtract_cfg != self.subtract_average:
            self.subtract_average = subtract_cfg

    def _baseline_maxlen(self) -> int:
        return max(1, min(self.average_window, self.max_history))

    def _reset_baseline(self) -> None:
        self.baseline_buffer = deque(maxlen=self._baseline_maxlen())

    def _append_baseline(self, amplitude: np.ndarray) -> None:
        target_len = self._baseline_maxlen()
        if self.baseline_buffer.maxlen != target_len:
            recent = list(self.baseline_buffer)[-target_len:]
            self.baseline_buffer = deque(recent, maxlen=target_len)

        self.baseline_buffer.append(np.array(amplitude, copy=True, dtype=np.float32))

    def _compute_baseline(self) -> np.ndarray:
        if not self.baseline_buffer:
            return np.zeros(self.num_bins, dtype=np.float32)

        buffer_array = np.array(self.baseline_buffer, dtype=np.float32)
        if buffer_array.ndim == 1:
            buffer_array = buffer_array[np.newaxis, :]

        with np.errstate(invalid='ignore'):
            baseline = np.nanmean(buffer_array, axis=0)

        baseline = np.where(np.isfinite(baseline), baseline, 0.0).astype(np.float32, copy=False)

        if baseline.size < self.num_bins:
            baseline = np.pad(baseline, (0, self.num_bins - baseline.size), constant_values=0.0)
        elif baseline.size > self.num_bins:
            baseline = baseline[:self.num_bins]

        return baseline

    def _assemble_history_matrix(self) -> np.ndarray:
        """Create a fixed-size matrix representing the history buffer."""
        num_cols = max(self.num_bins, 1)
        matrix = np.full((self.max_history, num_cols), np.nan, dtype=np.float32)

        if not self.history:
            return matrix

        history_array = np.array(self.history, dtype=np.float32)
        rows = history_array.shape[0]
        cols = min(history_array.shape[1], num_cols)
        matrix[-rows:, :cols] = history_array[:, :cols]
        return matrix

    def _refresh_empty_image(self) -> None:
        """Populate the data source with an empty matrix matching current axes."""
        if self.image_source is None:
            return

        num_cols = max(self.num_bins, 1)
        empty_matrix = np.full((self.max_history, num_cols), np.nan, dtype=np.float32)
        self.image_source.data = {
            'image': [empty_matrix],
            'x': [self.x_start],
            'y': [0.0],
            'dw': [self.x_end - self.x_start],
            'dh': [self._get_time_span()]
        }

    def _extract_range_profile(self, radar_data: RadarData) -> tuple[np.ndarray, np.ndarray]:
        """Extract magnitude (dB) range profile and range axis."""
        has_complex = getattr(radar_data, 'adc_complex', None) is not None and len(radar_data.adc_complex) > 0
        has_regular = getattr(radar_data, 'adc', None) is not None and len(radar_data.adc) > 0

        use_complex = (
            getattr(self.scene_config, 'range_profile_mode', 'log_magnitude') == 'complex' and
            has_complex
        )

        amplitude_db = np.array([])
        range_bins = np.array([])

        try:
            if use_complex:
                range_bins, magnitude_db, _ = radar_data.get_complex_range_profile()
                amplitude_db = magnitude_db
            elif has_regular:
                magnitude_db = radar_data.adc.astype(np.float32) / 100.0
                range_bins = np.arange(len(magnitude_db))
                amplitude_db = magnitude_db
            elif has_complex:
                range_bins, magnitude_db, _ = radar_data.get_complex_range_profile()
                amplitude_db = magnitude_db
        except Exception as e:
            logger.error(f"RangeWaterfallPlot: Error extracting range profile data: {e}")
            return np.array([]), np.array([])

        if amplitude_db.size == 0:
            return np.array([]), np.array([])

        amplitude_db = np.asarray(amplitude_db, dtype=np.float32)
        amplitude_db[~np.isfinite(amplitude_db)] = np.nan

        range_axis = self._get_range_axis(radar_data, len(amplitude_db))
        if range_axis.size == 0:
            range_axis = np.asarray(range_bins, dtype=np.float32)

        min_len = min(len(amplitude_db), len(range_axis))
        return amplitude_db[:min_len], range_axis[:min_len]

    def _get_range_axis(self, radar_data: RadarData, data_length: int) -> np.ndarray:
        """Compute range axis in meters if possible."""
        if radar_data.config_params:
            range_step = radar_data.config_params.get('rangeStep')
            if range_step is not None:
                try:
                    step_value = float(range_step)
                    return np.arange(data_length, dtype=np.float32) * step_value
                except (TypeError, ValueError):
                    logger.warning("RangeWaterfallPlot: Invalid rangeStep value %s", range_step)
        return np.array([])

    def _get_range_step(self, radar_data: RadarData) -> float:
        """Best-effort extraction of range step size in meters."""
        if radar_data.config_params:
            range_step = radar_data.config_params.get('rangeStep')
            if range_step is not None:
                try:
                    step_value = float(range_step)
                    if step_value > 0:
                        return step_value
                except (TypeError, ValueError):
                    logger.warning("RangeWaterfallPlot: Failed to parse rangeStep %s", range_step)
        fallback = getattr(self.scene_config, 'range_resolution_m', 0.1)
        try:
            fallback = float(fallback)
        except (TypeError, ValueError):
            fallback = 0.1
        return fallback if fallback > 0 else 0.1

    def _get_time_step(self, radar_data: RadarData) -> float:
        """Return frame period in seconds, falling back to frame rate if needed."""
        period_ms = None
        if radar_data.config_params:
            period_ms = (radar_data.config_params.get('framePeriod') or
                         radar_data.config_params.get('frame_period') or
                         radar_data.config_params.get('framePeriodicity'))
        if period_ms is not None:
            try:
                period_value = float(period_ms)
                if period_value > 0:
                    return period_value / 1000.0
            except (TypeError, ValueError):
                logger.warning("RangeWaterfallPlot: Unable to parse frame period %s", period_ms)

        frame_rate = getattr(self.scene_config, 'frame_rate_fps', None)
        if frame_rate:
            try:
                frame_rate = float(frame_rate)
                if frame_rate > 0:
                    return 1.0 / frame_rate
            except (TypeError, ValueError):
                logger.warning("RangeWaterfallPlot: Invalid frame_rate_fps %s", frame_rate)

        return 0.1

    def _update_time_axis(self) -> None:
        """Update the y-axis to reflect the configured time step."""
        if self._figure is not None and self.time_step:
            span = self._get_time_span()
            self._figure.y_range.start = 0.0
            self._figure.y_range.end = span
            self._figure.yaxis.axis_label = 'Time (s)'

    def _get_time_span(self) -> float:
        """Return the total time span represented by the waterfall plot."""
        step = self.time_step if self.time_step and self.time_step > 0 else 1.0
        return step * self.max_history

    def _clear_plot(self) -> None:
        """Reset the plot to its baseline state without collapsing the axes."""
        self.history.clear()
        self._reset_baseline()

        if self.image_source is not None:
            num_cols = max(self.num_bins, 1)
            empty_matrix = np.full((self.max_history, num_cols), np.nan, dtype=np.float32)
            self.image_source.data = {
                'image': [empty_matrix],
                'x': [self.x_start],
                'y': [0.0],
                'dw': [self.x_end - self.x_start],
                'dh': [self._get_time_span()]
            }

        if self.color_mapper is not None:
            self.color_mapper.low = 0.0
            self.color_mapper.high = 1.0

class RangeDopplerPlot(BasePlot):
    """Range-Doppler heatmap plot."""
    def _setup_plot(self) -> pn.pane.Bokeh:
        p = figure(
            title='Range-Doppler Heatmap',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            x_axis_label='Doppler (m/s)',
            y_axis_label='Range (m)',
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above',
            match_aspect=True,
        )
        self.data_source = ColumnDataSource({'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]})
        self.color_mapper = LinearColorMapper(palette=Viridis256, low=0, high=1)
        self.heatmap = p.image(
            image='image', x='x', y='y', dw='dw', dh='dh', source=self.data_source, color_mapper=self.color_mapper
        )
        color_bar = ColorBar(color_mapper=self.color_mapper, label_standoff=12, location=(0, 0), title='dB')
        p.add_layout(color_bar, 'right')
        return pn.pane.Bokeh(p)

    def update(self, radar_data: 'RadarData') -> None:
        """Update the range-Doppler heatmap plot with new radar data."""
        try:
            if not hasattr(radar_data, 'get_range_doppler_heatmap') or not radar_data.config_params:
                logger.debug("RangeDopplerPlot: Missing get_range_doppler_heatmap method or config_params")
                return
                
            heatmap_db, range_axis, velocity_axis = radar_data.get_range_doppler_heatmap()
            
            if heatmap_db.size == 0:
                logger.debug("RangeDopplerPlot: Empty heatmap data")
                self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                return
            
            logger.debug(f"RangeDopplerPlot: Heatmap shape: {heatmap_db.shape}, range_axis: {range_axis.shape}, velocity_axis: {velocity_axis.shape}")
            
            # Check for invalid data
            if np.any(np.isnan(heatmap_db)) or np.any(np.isinf(heatmap_db)):
                logger.warning("RangeDopplerPlot: Heatmap contains NaN or Inf values, using zeros")
                heatmap_db = np.zeros_like(heatmap_db)
            
            # Apply fftshift to center the zero velocity in the middle of the plot
            # Shift along axis 1 (velocity/Doppler axis)
            try:
                heatmap_db_shifted = np.fft.fftshift(heatmap_db, axes=1)
                logger.debug(f"RangeDopplerPlot: Applied fftshift, shape: {heatmap_db_shifted.shape}")
            except Exception as e:
                logger.error(f"RangeDopplerPlot: Error applying fftshift: {e}")
                heatmap_db_shifted = heatmap_db  # Use unshifted data as fallback
            
            # Calculate min/max values safely
            try:
                vmin = float(np.nanmin(heatmap_db_shifted))
                vmax = float(np.nanmax(heatmap_db_shifted))
                
                # Handle case where all values are the same
                if vmin == vmax:
                    vmax = vmin + 1
                    
                logger.debug(f"RangeDopplerPlot: Value range: {vmin:.2f} to {vmax:.2f}")
                
                # Update color mapper
                self.heatmap.glyph.color_mapper.low = vmin
                self.heatmap.glyph.color_mapper.high = vmax
                
            except Exception as e:
                logger.error(f"RangeDopplerPlot: Error calculating value range: {e}")
                # Use default range
                self.heatmap.glyph.color_mapper.low = 0
                self.heatmap.glyph.color_mapper.high = 1
            
            # Update data source
            try:
                # Ensure axes have valid values
                if len(velocity_axis) == 0 or len(range_axis) == 0:
                    logger.warning("RangeDopplerPlot: Empty velocity or range axis")
                    self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                    return
                
                # Ensure we have valid bounds
                x_start = float(velocity_axis[0])
                x_end = float(velocity_axis[-1])
                y_start = float(range_axis[0])
                y_end = float(range_axis[-1])
                
                # Handle case where start and end are the same
                if x_start == x_end:
                    x_end = x_start + 1
                if y_start == y_end:
                    y_end = y_start + 1
                
                logger.debug(f"RangeDopplerPlot: Updating data source with bounds: x=[{x_start:.3f}, {x_end:.3f}], y=[{y_start:.3f}, {y_end:.3f}]")
                
                self.data_source.data = {
                    'image': [heatmap_db_shifted],
                    'x': [x_start],
                    'y': [y_start],
                    'dw': [x_end - x_start],
                    'dh': [y_end - y_start]
                }
                
                logger.debug("RangeDopplerPlot: Successfully updated data source")
                
            except Exception as e:
                logger.error(f"RangeDopplerPlot: Error updating data source: {e}")
                # Fallback to empty data
                self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                
        except Exception as e:
            logger.error(f"RangeDopplerPlot: Unexpected error in update: {e}")
            # Ensure we don't leave the plot in a broken state
            self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}


class RangeAzimuthPlot(BasePlot):
    """Range-azimuth heatmap plot."""
    def _setup_plot(self) -> pn.pane.Bokeh:
        p = figure(
            title='Range-Azimuth Heatmap',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            x_axis_label='Azimuth (degrees)',
            y_axis_label='Range (m)',
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above',
            match_aspect=True,
        )
        self.data_source = ColumnDataSource({'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]})
        self.color_mapper = LinearColorMapper(palette=Viridis256, low=0, high=1)
        self.heatmap = p.image(
            image='image', x='x', y='y', dw='dw', dh='dh', source=self.data_source, color_mapper=self.color_mapper
        )
        color_bar = ColorBar(color_mapper=self.color_mapper, label_standoff=12, location=(0, 0), title='dB')
        p.add_layout(color_bar, 'right')
        return pn.pane.Bokeh(p)

    def update(self, radar_data: 'RadarData') -> None:
        """Update the range-azimuth heatmap plot with new radar data."""
        try:
            if not hasattr(radar_data, 'get_range_azimuth_heatmap') or not radar_data.config_params:
                logger.debug("RangeAzimuthPlot: Missing get_range_azimuth_heatmap method or config_params")
                return
                
            heatmap_db, range_axis, azimuth_axis = radar_data.get_range_azimuth_heatmap()
            
            if heatmap_db.size == 0:
                logger.debug("RangeAzimuthPlot: Empty heatmap data")
                self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                return
            
            logger.debug(f"RangeAzimuthPlot: Heatmap shape: {heatmap_db.shape}, range_axis: {range_axis.shape}, azimuth_axis: {azimuth_axis.shape}")
            
            # Check for invalid data
            if np.any(np.isnan(heatmap_db)) or np.any(np.isinf(heatmap_db)):
                logger.warning("RangeAzimuthPlot: Heatmap contains NaN or Inf values, using zeros")
                heatmap_db = np.zeros_like(heatmap_db)
            
            # Apply fftshift to center the zero azimuth in the middle of the plot
            # Shift along axis 1 (azimuth axis)
            try:
                heatmap_db_shifted = np.fft.fftshift(heatmap_db, axes=1)
                logger.debug(f"RangeAzimuthPlot: Applied fftshift, shape: {heatmap_db_shifted.shape}")
            except Exception as e:
                logger.error(f"RangeAzimuthPlot: Error applying fftshift: {e}")
                heatmap_db_shifted = heatmap_db  # Use unshifted data as fallback
            
            # Calculate min/max values safely
            try:
                vmin = float(np.nanmin(heatmap_db_shifted))
                vmax = float(np.nanmax(heatmap_db_shifted))
                
                # Handle case where all values are the same
                if vmin == vmax:
                    vmax = vmin + 1
                    
                logger.debug(f"RangeAzimuthPlot: Value range: {vmin:.2f} to {vmax:.2f}")
                
                # Update color mapper
                self.heatmap.glyph.color_mapper.low = vmin
                self.heatmap.glyph.color_mapper.high = vmax
                
            except Exception as e:
                logger.error(f"RangeAzimuthPlot: Error calculating value range: {e}")
                # Use default range
                self.heatmap.glyph.color_mapper.low = 0
                self.heatmap.glyph.color_mapper.high = 1
            
            # Update data source
            try:
                # Ensure axes have valid values
                if len(azimuth_axis) == 0 or len(range_axis) == 0:
                    logger.warning("RangeAzimuthPlot: Empty azimuth or range axis")
                    self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                    return
                
                # Ensure we have valid bounds
                x_start = float(azimuth_axis[0])
                x_end = float(azimuth_axis[-1])
                y_start = float(range_axis[0])
                y_end = float(range_axis[-1])
                
                # Handle case where start and end are the same
                if x_start == x_end:
                    x_end = x_start + 1
                if y_start == y_end:
                    y_end = y_start + 1
                
                logger.debug(f"RangeAzimuthPlot: Updating data source with bounds: x=[{x_start:.3f}, {x_end:.3f}], y=[{y_start:.3f}, {y_end:.3f}]")
                
                self.data_source.data = {
                    'image': [heatmap_db_shifted],
                    'x': [x_start],
                    'y': [y_start],
                    'dw': [x_end - x_start],
                    'dh': [y_end - y_start]
                }
                
                logger.debug("RangeAzimuthPlot: Successfully updated data source")
                
            except Exception as e:
                logger.error(f"RangeAzimuthPlot: Error updating data source: {e}")
                # Fallback to empty data
                self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
                
        except Exception as e:
            logger.error(f"RangeAzimuthPlot: Unexpected error in update: {e}")
            # Ensure we don't leave the plot in a broken state
            self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}


class PolarRangePlot(BasePlot):
    """Polar plot for visualizing the first peak in range profile complex data."""
    
    def _setup_plot(self) -> pn.pane.Bokeh:
        """Set up the polar plot."""
        p = figure(
            title='Polar Range Profile - First Peak Complex Data',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            x_range=(-1.2, 1.2),
            y_range=(-1.2, 1.2),
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above',
            match_aspect=True
        )
        
        # Data source for polar plot points
        self.polar_data_source = ColumnDataSource({
            'x': [],
            'y': [],
            'magnitude': [],
            'range_bin': []
        })
        
        # Data source for magnitude circle
        self.circle_data_source = ColumnDataSource({
            'x': [],
            'y': []
        })
        
        # Data source for range bin labels
        self.label_data_source = ColumnDataSource({
            'x': [],
            'y': [],
            'text': []
        })
        
        # Create color mapper for magnitude values
        self.color_mapper = LinearColorMapper(palette=Viridis256, low=0, high=1)
        
        # Scatter plot for complex values
        self.scatter_glyph = p.scatter(
            x='x',
            y='y',
            size=8,
            fill_color={'field': 'magnitude', 'transform': self.color_mapper},
            line_color='white',
            line_width=1,
            alpha=0.8,
            source=self.polar_data_source,
            name='complex_values'
        )
        
        # Circle outline showing magnitude
        self.circle_line = p.line(
            x='x',
            y='y',
            line_width=2,
            color='red',
            alpha=0.7,
            source=self.circle_data_source,
            name='magnitude_circle'
        )
        
        # Text labels for range bins
        from bokeh.models import LabelSet
        self.labels = LabelSet(
            x='x', y='y', text='text',
            x_offset=5, y_offset=5,
            source=self.label_data_source,
            text_font_size='8pt',
            text_color='black'
        )
        p.add_layout(self.labels)
        
        # Add color bar
        color_bar = ColorBar(
            color_mapper=self.color_mapper,
            title='Magnitude (norm.)',
            location=(0, 0)
        )
        p.add_layout(color_bar, 'right')
        
        # Add coordinate system lines
        p.line([-1.2, 1.2], [0, 0], line_width=1, color='gray', alpha=0.5)  # X-axis
        p.line([0, 0], [-1.2, 1.2], line_width=1, color='gray', alpha=0.5)  # Y-axis
        
        # Add unit circle
        circle_angles = np.linspace(0, 2*np.pi, 100)
        circle_x = np.cos(circle_angles)
        circle_y = np.sin(circle_angles)
        p.line(circle_x, circle_y, line_width=1, color='gray', alpha=0.3, line_dash='dashed')
        
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'normal'
        p.xaxis.axis_label = 'Real Part (normalized)'
        p.yaxis.axis_label = 'Imaginary Part (normalized)'
        
        p.grid.grid_line_alpha = 0.3
        
        return pn.pane.Bokeh(p)
    
    def update(self, radar_data: RadarData) -> None:
        """Update the polar plot with new radar data."""
        if not radar_data:
            return
            
        try:
            # Check if complex range profile data is available
            if not hasattr(radar_data, 'adc_complex') or radar_data.adc_complex is None or len(radar_data.adc_complex) == 0:
                logger.debug("PolarRangePlot: No complex range profile data available")
                self._clear_plot()
                return
            
            # Get complex range profile data
            range_bins, magnitude_dB, phase = radar_data.get_complex_range_profile()
            
            if len(range_bins) == 0 or len(magnitude_dB) == 0:
                logger.debug("PolarRangePlot: Empty complex range profile data")
                self._clear_plot()
                return
            
            # Find the first significant peak (ignore DC component at bin 0)
            # Use magnitude in linear scale for peak detection
            magnitude_linear = np.abs(radar_data.adc_complex)
            
            # Ignore the first few bins to skip DC and near-DC components
            start_bin = max(2, int(0.02 * len(magnitude_linear)))  # Skip first 2% of bins or at least 2 bins
            search_magnitude = magnitude_linear[start_bin:]
            
            if len(search_magnitude) == 0:
                logger.debug("PolarRangePlot: No range bins available after skipping DC")
                self._clear_plot()
                return
            
            # Find peaks in the magnitude profile
            peaks, properties = find_peaks(search_magnitude, height=np.max(search_magnitude) * 0.1, distance=5)
            
            if len(peaks) == 0:
                logger.debug("PolarRangePlot: No significant peaks found in range profile")
                self._clear_plot()
                return
            
            # Get the first peak (relative to the search start)
            first_peak_idx = peaks[0] + start_bin
            peak_magnitude = magnitude_linear[first_peak_idx]
            
            logger.debug(f"PolarRangePlot: Found first peak at range bin {first_peak_idx} with magnitude {peak_magnitude:.2f}")
            
            # Get a window around the peak to show complex behavior
            window_size = 15  # Show ±15 bins around the peak
            start_idx = max(0, first_peak_idx - window_size)
            end_idx = min(len(radar_data.adc_complex), first_peak_idx + window_size + 1)
            
            # Extract complex values around the peak
            complex_values = radar_data.adc_complex[start_idx:end_idx]
            range_bin_indices = np.arange(start_idx, end_idx)
            
            if len(complex_values) == 0:
                self._clear_plot()
                return
            
            # Normalize complex values for better visualization
            max_magnitude = np.max(np.abs(complex_values))
            if max_magnitude > 0:
                normalized_complex = complex_values / max_magnitude
            else:
                normalized_complex = complex_values
            
            # Extract real and imaginary parts
            x_coords = np.real(normalized_complex)
            y_coords = np.imag(normalized_complex)
            
            # Calculate magnitude for color mapping
            magnitudes = np.abs(normalized_complex)
            
            # Update scatter plot data
            self.polar_data_source.data = {
                'x': x_coords,
                'y': y_coords,
                'magnitude': magnitudes,
                'range_bin': range_bin_indices
            }
            
            # Update color mapper range
            if len(magnitudes) > 0:
                self.color_mapper.low = float(np.min(magnitudes))
                self.color_mapper.high = float(np.max(magnitudes))
            
            # Create magnitude circle for the peak
            if peak_magnitude > 0:
                peak_normalized_magnitude = np.abs(normalized_complex[first_peak_idx - start_idx])
                circle_angles = np.linspace(0, 2*np.pi, 100)
                circle_x = peak_normalized_magnitude * np.cos(circle_angles)
                circle_y = peak_normalized_magnitude * np.sin(circle_angles)
                
                self.circle_data_source.data = {
                    'x': circle_x,
                    'y': circle_y
                }
            else:
                self.circle_data_source.data = {'x': [], 'y': []}
            
            # Add labels for some key points
            label_indices = [0, len(x_coords)//2, len(x_coords)-1] if len(x_coords) > 2 else [0]
            label_x = [x_coords[i] for i in label_indices if i < len(x_coords)]
            label_y = [y_coords[i] for i in label_indices if i < len(y_coords)]
            label_text = [f"R{range_bin_indices[i]}" for i in label_indices if i < len(range_bin_indices)]
            
            self.label_data_source.data = {
                'x': label_x,
                'y': label_y,
                'text': label_text
            }
            
        except Exception as e:
            logger.error(f"Error updating polar range plot: {e}")
            self._clear_plot()
    
    def _clear_plot(self):
        """Clear all plot data."""
        self.polar_data_source.data = {'x': [], 'y': [], 'magnitude': [], 'range_bin': []}
        self.circle_data_source.data = {'x': [], 'y': []}
        self.label_data_source.data = {'x': [], 'y': [], 'text': []}


class PlotManager:
    """Manager for handling multiple visualization tabs in the radar GUI."""
    
    def __init__(self, scene_config: RadarConfig, display_config: 'DisplayConfig', main_plot: pn.pane.Bokeh):
        """
        Initialize the plot manager.
        
        Parameters
        ----------
        scene_config : SceneProfileConfig
            Configuration for the radar scene
        display_config : DisplayConfig
            Configuration for display settings
        main_plot : pn.pane.Bokeh
            The main scatter plot to include in the tabs
        """
        self.scene_config = scene_config
        self.display_config = display_config
        self.main_plot = main_plot
        
        # Initialize plots
        self.scatter_plot = ScatterPlot(scene_config, display_config)
        self.range_profile_plot = RangeProfilePlot(scene_config, display_config)
        self.range_waterfall_plot = RangeWaterfallPlot(scene_config, display_config) if getattr(scene_config, 'plot_range_waterfall', False) else None
        self.range_doppler_plot = RangeDopplerPlot(scene_config, display_config)
        self.range_azimuth_plot = RangeAzimuthPlot(scene_config, display_config)
        self.polar_range_plot = PolarRangePlot(scene_config, display_config)
        
        # Create tabs
        tabs = [
            ('Point Cloud', self.scatter_plot.view)
        ]
        if scene_config.plot_range_profile:
            tabs.append(('Range Profile', self.range_profile_plot.view))
        if getattr(scene_config, 'plot_range_waterfall', False) and self.range_waterfall_plot is not None:
            tabs.append(('Range Waterfall', self.range_waterfall_plot.view))
        if scene_config.plot_range_doppler_heat_map:
            tabs.append(('Range-Doppler', self.range_doppler_plot.view))
        if scene_config.plot_range_azimuth_heat_map:
            tabs.append(('Range-Azimuth', self.range_azimuth_plot.view))
        # Always add polar plot if complex range profile data is available
        tabs.append(('Polar Range', self.polar_range_plot.view))
        self.tabs = pn.Tabs(*tabs)
        self.view = self.tabs
    
    def update(self, radar_data: RadarData):
        """
        Update all plots with new radar data.
        
        Parameters
        ----------
        radar_data : RadarData
            The radar data object for the current frame.
        """
        if not radar_data:
            logger.debug("PlotManager.update received no radar_data.")
            return

        try:
            logger.debug("PlotManager: Starting plot updates")
            
            # Update scatter plot
            try:
                self.scatter_plot.update(radar_data)
                logger.debug("PlotManager: Scatter plot updated successfully")
            except Exception as e:
                logger.error(f"PlotManager: Error updating scatter plot: {e}")
            
            # Update range profile plot if enabled
            if self.scene_config.plot_range_profile:
                try:
                    self.range_profile_plot.update(radar_data)
                    logger.debug("PlotManager: Range profile plot updated successfully")
                except Exception as e:
                    logger.error(f"PlotManager: Error updating range profile plot: {e}")

            if getattr(self.scene_config, 'plot_range_waterfall', False) and self.range_waterfall_plot is not None:
                try:
                    self.range_waterfall_plot.update(radar_data)
                    logger.debug("PlotManager: Range waterfall plot updated successfully")
                except Exception as e:
                    logger.error(f"PlotManager: Error updating range waterfall plot: {e}")
            
            # Update range-Doppler plot if enabled
            if self.scene_config.plot_range_doppler_heat_map:
                try:
                    self.range_doppler_plot.update(radar_data)
                    logger.debug("PlotManager: Range-Doppler plot updated successfully")
                except Exception as e:
                    logger.error(f"PlotManager: Error updating range-Doppler plot: {e}")
            
            # Update range-azimuth plot if enabled
            if self.scene_config.plot_range_azimuth_heat_map:
                try:
                    self.range_azimuth_plot.update(radar_data)
                    logger.debug("PlotManager: Range-azimuth plot updated successfully")
                except Exception as e:
                    logger.error(f"PlotManager: Error updating range-azimuth plot: {e}")
            
            # Update polar range plot
            try:
                self.polar_range_plot.update(radar_data)
                logger.debug("PlotManager: Polar range plot updated successfully")
            except Exception as e:
                logger.error(f"PlotManager: Error updating polar range plot: {e}")
                    
            logger.debug("PlotManager: All plot updates completed")
            
        except Exception as e:
            logger.error(f"PlotManager: Unexpected error in update: {e}")
            # Don't let the error propagate and freeze the GUI 
