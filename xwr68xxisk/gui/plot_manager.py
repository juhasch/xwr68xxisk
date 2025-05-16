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
from ..radar_config_models import SceneProfileConfig, DisplayConfig
from ..parse import RadarData

# Initialize logger
logger = logging.getLogger(__name__)

# Initialize extensions
hv.extension('bokeh')
pn.extension(design="material", sizing_mode="stretch_width")


class BasePlot(param.Parameterized):
    """Base class for all plot types."""
    
    def __init__(self, scene_config: SceneProfileConfig, display_config: DisplayConfig):
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
            title='Range Profile',
            width=self.display_config.plot_width,
            height=self.display_config.plot_height,
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above'
        )
        
        self.data_source = ColumnDataSource({
            'range': [],
            'magnitude': []
        })
        
        p.line(
            x='range',
            y='magnitude',
            line_width=2,
            source=self.data_source,
            name='range_profile'
        )
        
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'normal'
        p.xaxis.axis_label = 'Range (m)'
        p.yaxis.axis_label = 'Magnitude (dB)'
        
        p.grid.grid_line_alpha = 0.3
        
        return pn.pane.Bokeh(p)
    
    def update(self, radar_data: RadarData) -> None:
        """Update the range profile plot with new radar data."""
        if not radar_data:
            return
            
        try:
            if radar_data.adc is not None and len(radar_data.adc) > 0:
                # Add a small epsilon to prevent log10(0) and ensure float type for log
                magnitude_data = 20 * np.log10(np.abs(radar_data.adc.astype(np.float32)) + 1e-9)

                range_axis = np.array([]) # Initialize
                if radar_data.config_params:
                    # rangeBins from config should define the expected length of adc data
                    # rangeStep is used to convert bin index to meters
                    # These should have been populated when RadarData was initialized
                    range_bins_config = radar_data.config_params.get('rangeBins')
                    range_step = radar_data.config_params.get('rangeStep')

                    if range_step is not None: # rangeBins_config can be used for validation if needed
                        actual_adc_len = len(radar_data.adc)
                        # if range_bins_config is not None and actual_adc_len != range_bins_config:
                        #    logger.warning(f"ADC data length {actual_adc_len} differs from configured rangeBins {range_bins_config}")
                        
                        # Create range axis based on actual ADC data length and configured step
                        range_axis = np.arange(actual_adc_len) * range_step
                    else:
                        logger.warning("rangeStep not in radar_data.config_params. Cannot compute range axis.")
                else:
                    logger.warning("radar_data.config_params is None or empty. Cannot compute range axis.")

                if len(range_axis) > 0 and len(magnitude_data) > 0 :
                    # Ensure data alignment by taking the minimum length
                    min_len = min(len(magnitude_data), len(range_axis))
                    self.data_source.data = {
                        'range': range_axis[:min_len],
                        'magnitude': magnitude_data[:min_len]
                    }
                else: # If range_axis or magnitude_data could not be computed or is empty
                    self.data_source.data = {'range': [], 'magnitude': []}
            else:
                self.data_source.data = {'range': [], 'magnitude': []}
            
        except Exception as e:
            logger.error(f"Error updating range profile plot: {e}")
            self.data_source.data = {'range': [], 'magnitude': []}


class PlotManager:
    """Manager for handling multiple visualization tabs in the radar GUI."""
    
    def __init__(self, scene_config: SceneProfileConfig, display_config: DisplayConfig, main_plot: pn.pane.Bokeh):
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
        
        # Create tabs
        self.tabs = pn.Tabs(
            ('Point Cloud', self.scatter_plot.view),
            ('Range Profile', self.range_profile_plot.view) if scene_config.plot_range_profile else None
        )
        
        # Create the main view
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

        # Update scatter plot
        if hasattr(self, 'scatter_plot') and self.scatter_plot:
            try:
                # logger.debug("PlotManager updating scatter_plot.")
                self.scatter_plot.update(radar_data)
            except Exception as e:
                logger.error(f"Error updating scatter plot via PlotManager: {e}")
    
        # Update range profile plot if it's enabled and exists
        if self.scene_config.plot_range_profile and hasattr(self, 'range_profile_plot') and self.range_profile_plot:
            try:
                # logger.debug("PlotManager updating range_profile_plot.")
                self.range_profile_plot.update(radar_data)
            except Exception as e:
                logger.error(f"Error updating range profile plot via PlotManager: {e}") 