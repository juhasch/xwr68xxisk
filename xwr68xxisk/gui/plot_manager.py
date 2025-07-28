"""
Plot manager for radar visualization.

This module provides a PlotManager class that manages multiple visualization tabs
for radar data, including scatter plots and range profiles.
"""

import logging
import numpy as np
import panel as pn
import holoviews as hv
import param
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, ColorBar, LinearColorMapper
from bokeh.layouts import column
from bokeh.palettes import Viridis256
from bokeh.transform import linear_cmap
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
                # Use complex range profile data - plot log magnitude
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
                # Use regular range profile data
                magnitude_data = 20 * np.log10(np.abs(radar_data.adc.astype(np.float32)) + 1e-9)
                range_axis = self._get_range_axis(radar_data, len(magnitude_data))
                
                if len(range_axis) > 0 and len(magnitude_data) > 0:
                    min_len = min(len(magnitude_data), len(range_axis))
                    self.range_data_source.data = {
                        'range': range_axis[:min_len],
                        'magnitude': magnitude_data[:min_len]
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
        if not hasattr(radar_data, 'get_range_doppler_heatmap') or not radar_data.config_params:
            return
        heatmap_db, range_axis, velocity_axis = radar_data.get_range_doppler_heatmap()
        if heatmap_db.size == 0:
            self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
            return
    
        # Apply fftshift to center the zero velocity in the middle of the plot
        # Shift along axis 1 (velocity/Doppler axis)
        heatmap_db_shifted = np.fft.fftshift(heatmap_db, axes=1)
        
        vmin = float(np.nanmin(heatmap_db_shifted))
        vmax = float(np.nanmax(heatmap_db_shifted))
        if vmin == vmax:
            vmax = vmin + 1
        self.heatmap.glyph.color_mapper.low = vmin
        self.heatmap.glyph.color_mapper.high = vmax
        self.data_source.data = {
            'image': [heatmap_db_shifted],
            'x': [velocity_axis[0]],
            'y': [range_axis[0]],
            'dw': [velocity_axis[-1] - velocity_axis[0]],
            'dh': [range_axis[-1] - range_axis[0]]
        }


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
        if not hasattr(radar_data, 'get_range_azimuth_heatmap') or not radar_data.config_params:
            return
        heatmap_db, range_axis, azimuth_axis = radar_data.get_range_azimuth_heatmap()
        if heatmap_db.size == 0:
            self.data_source.data = {'image': [np.zeros((10, 10))], 'x': [0], 'y': [0], 'dw': [1], 'dh': [1]}
            return
        
        # Apply fftshift to center the zero azimuth in the middle of the plot
        # Shift along axis 1 (azimuth axis)
        heatmap_db_shifted = np.fft.fftshift(heatmap_db, axes=1)
        
        vmin = float(np.nanmin(heatmap_db_shifted))
        vmax = float(np.nanmax(heatmap_db_shifted))
        if vmin == vmax:
            vmax = vmin + 1
        self.heatmap.glyph.color_mapper.low = vmin
        self.heatmap.glyph.color_mapper.high = vmax
        self.data_source.data = {
            'image': [heatmap_db_shifted],
            'x': [azimuth_axis[0]],
            'y': [range_axis[0]],
            'dw': [azimuth_axis[-1] - azimuth_axis[0]],
            'dh': [range_axis[-1] - range_axis[0]]
        }


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
        self.range_doppler_plot = RangeDopplerPlot(scene_config, display_config)
        self.range_azimuth_plot = RangeAzimuthPlot(scene_config, display_config)
        
        # Create tabs
        tabs = [
            ('Point Cloud', self.scatter_plot.view)
        ]
        if scene_config.plot_range_profile:
            tabs.append(('Range Profile', self.range_profile_plot.view))
        if scene_config.plot_range_doppler_heat_map:
            tabs.append(('Range-Doppler', self.range_doppler_plot.view))
        if scene_config.plot_range_azimuth_heat_map:
            tabs.append(('Range-Azimuth', self.range_azimuth_plot.view))
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
            self.scatter_plot.update(radar_data)
            if self.scene_config.plot_range_profile:
                self.range_profile_plot.update(radar_data)
            if self.scene_config.plot_range_doppler_heat_map:
                self.range_doppler_plot.update(radar_data)
            if self.scene_config.plot_range_azimuth_heat_map:
                self.range_azimuth_plot.update(radar_data)
        except Exception as e:
            logger.error(f"Error updating plots: {e}") 