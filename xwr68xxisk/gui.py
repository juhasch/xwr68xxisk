"""
Interactive GUI for xwr68xxisk radar sensor evaluation kit.

This module provides a Bokeh-based GUI for visualizing and controlling 
the Texas Instruments xwr68xxisk radar sensor. It includes real-time point cloud 
visualization, clustering, tracking, camera integration, and recording functionality.
"""

# Standard library imports
import os
import logging
import time
from datetime import datetime

# Third-party imports
import numpy as np
import panel as pn
import holoviews as hv
import colorcet as cc
from bokeh.plotting import figure
from bokeh.models import ColorBar, LinearColorMapper, ColumnDataSource, LabelSet
from panel.widgets import TextAreaInput, Button

# Local imports
from xwr68xxisk.radar import RadarConnection, create_radar, RadarConnectionError
from xwr68xxisk.parse import RadarData
from xwr68xxisk.clustering import PointCloudClustering
from xwr68xxisk.tracking import PointCloudTracker
from xwr68xxisk.configs import ConfigManager
from xwr68xxisk.record import PointCloudRecorder
from xwr68xxisk.cameras import BaseCamera
from xwr68xxisk.camera_recorder import CameraRecorder

logger = logging.getLogger(__name__)

# Initialize extensions
hv.extension('bokeh')
pn.extension(design="material", sizing_mode="stretch_width")


class RadarGUI:
    """
    Interactive GUI for xwr68xxisk radar sensor.
    
    This class provides a complete GUI interface for controlling and visualizing 
    data from the Texas Instruments xwr68xxisk radar sensor evaluation kit. 
    It includes real-time point cloud visualization, clustering, tracking, and 
    recording capabilities.
    
    The GUI is built using Panel and Bokeh for interactive visualization.
    
    Attributes
    ----------
    config_manager : ConfigManager
        Manager for handling radar configuration
    radar : RadarConnection
        Connection to the radar sensor
    camera : BaseCamera, optional
        Connection to the camera, if enabled
    is_running : bool
        Whether the radar is currently running
    is_recording : bool
        Whether recording is currently active
    enable_clustering : bool
        Whether clustering is enabled
    enable_tracking : bool
        Whether tracking is enabled
    
    Notes
    -----
    The GUI initializes in a disconnected state. The user must first connect
    to the radar sensor before starting visualization and recording.
    """
    def __init__(self):
        # Initialize configuration
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()
        
        # Initialize radar connection
        self.radar = None
        self.radar_type = None
        self.radar_data = None
        
        # Set default profile path
        self.config_file = os.path.join('configs', 'user_profile.cfg')
        # Create configs directory if it doesn't exist
        os.makedirs('configs', exist_ok=True)
        # Create default profile if it doesn't exist
        if not os.path.exists(self.config_file):
            with open(self.config_file, 'w') as f:
                f.write("% Default radar profile\n% This file can be modified or replaced using the 'Load Profile' button\n")
        
        # Initialize camera
        self.camera = None
        self.camera_source = ColumnDataSource({'image': [], 'dw': [], 'dh': []})
        self.camera_plot = None
        self.camera_running = False
        
        # Create all control widgets first
        self.load_config_button = pn.widgets.FileInput(name='Load Profile', accept='.cfg')
        self.connect_button = pn.widgets.Button(name='Connect to Sensor', button_type='primary')
        self.start_button = pn.widgets.Button(name='Start', button_type='primary')
        self.stop_button = pn.widgets.Button(name='Stop', button_type='danger')
        self.record_button = pn.widgets.Button(name='Start Recording', button_type='primary')
        self.exit_button = pn.widgets.Button(name='Exit', button_type='danger')
        self.config_button = Button(name="Configure Profile", button_type="primary", disabled=True)
        
        # Create camera controls
        self.camera_select = pn.widgets.Select(
            name='Camera Device',
            value='0',
            options=['0', '1', '2'],
            width=100
        )
        self.camera_button = pn.widgets.Button(
            name='Start Camera',
            button_type='primary'
        )
        
        # Create camera focus controls
        self.camera_autofocus = pn.widgets.Checkbox(name='Auto Focus', value=True)
        self.camera_focus = pn.widgets.IntSlider(name='Focus', start=0, end=255, value=0, step=1, disabled=True)
        
        # Add recording format selection
        self.record_format_select = pn.widgets.RadioButtonGroup(
            name='Recording Format',
            options=['CSV', 'PCD'],
            value='CSV',
            button_type='default'
        )
        
        # Parameters panel controls
        self.modify_params_checkbox = pn.widgets.Checkbox(name='Modify Parameters', value=False)
        self.clutter_removal_checkbox = pn.widgets.Checkbox(
            name='Static Clutter Removal',
            value=False,  # Will be set when radar is connected
            disabled=True  # Initially disabled until connected
        )
        self.frame_period_slider = pn.widgets.FloatSlider(
            name='Frame Period (ms)',
            start=50,
            end=1000,
            value=self.config.processing.frame_period_ms,
            step=10,
            disabled=True  # Initially disabled until connected
        )
        self.mob_enabled_checkbox = pn.widgets.Checkbox(
            name='Multi-object Beamforming',
            value=False,  # Will be set when radar is connected
            disabled=True  # Initially disabled until connected
        )
        self.mob_threshold_slider = pn.widgets.FloatSlider(
            name='MOB Threshold',
            start=0,
            end=1,
            value=0.5,  # Will be set when radar is connected
            step=0.01,
            disabled=True  # Initially disabled until connected
        )
        
        # Add clustering and tracking controls
        self.clustering_checkbox = pn.widgets.Checkbox(
            name='Enable Clustering',
            value=self.config.clustering.enabled
        )
        self.tracking_checkbox = pn.widgets.Checkbox(
            name='Enable Tracking',
            value=self.config.tracking.enabled
        )
        self.cluster_eps_slider = pn.widgets.FloatSlider(
            name='Cluster Size (m)',
            start=0.1,
            end=2.0,
            value=self.config.clustering.eps,
            step=0.1
        )
        self.cluster_min_samples_slider = pn.widgets.IntSlider(
            name='Min Points per Cluster',
            start=3,
            end=20,
            value=self.config.clustering.min_samples,
            step=1
        )
        self.track_max_distance_slider = pn.widgets.FloatSlider(
            name='Max Track Distance (m)',
            start=0.5,
            end=5.0,
            value=self.config.tracking.max_distance,
            step=0.1
        )
        self.track_min_hits_slider = pn.widgets.IntSlider(
            name='Min Track Hits',
            start=2,
            end=10,
            value=self.config.tracking.min_hits,
            step=1
        )
        self.track_max_misses_slider = pn.widgets.IntSlider(
            name='Max Track Misses',
            start=2,
            end=10,
            value=self.config.tracking.max_misses,
            step=1
        )
        
        # Create floating panel for parameters
        self.params_panel = pn.layout.FloatPanel(
            pn.Column(
                self.clutter_removal_checkbox,
                self.frame_period_slider,
                self.mob_enabled_checkbox,
                self.mob_threshold_slider,
                pn.layout.Divider(),
                pn.pane.Markdown('## Camera Settings'),
                self.camera_autofocus,
                self.camera_focus,
                pn.layout.Divider(),
                pn.pane.Markdown('## Clustering & Tracking'),
                self.clustering_checkbox,
                self.cluster_eps_slider,
                self.cluster_min_samples_slider,
                pn.layout.Divider(),
                self.tracking_checkbox,
                self.track_max_distance_slider,
                self.track_min_hits_slider,
                self.track_max_misses_slider
            ),
            name='Radar Parameters',
            margin=20,
            width=300,
            position='right-top',
            visible=False,
            styles={
                'position': 'fixed',
                'top': '80px',
                'right': '20px',
                'z-index': '1000',
                'background': 'white',
                'border': '1px solid #ddd',
                'border-radius': '5px',
                'box-shadow': '0 2px 4px rgba(0,0,0,0.1)'
            }
        )
        
        # Create configuration modal components
        self.config_modal = pn.Column(
            pn.Row(
                pn.pane.Markdown('## Sensor Profile'),
                pn.layout.HSpacer(),
                pn.widgets.Button(name='✕', width=30, align='end'),
                sizing_mode='stretch_width'
            ),
            TextAreaInput(
                name="Profile Settings",
                height=300,
                width=750,
                value="",  # Will be loaded from file
            ),
            pn.Row(
                Button(name="Save", button_type="primary", width=100),
                Button(name="Cancel", width=100),
            ),
            TextAreaInput(
                name="**Sensor Information**",
                value="Connect to sensor to see version information",
                height=200,
                disabled=True,
                styles={
                    'font-family': 'monospace',
                    'white-space': 'pre',
                    'overflow': 'auto',
                    'resize': 'none',
                    'color': '#000000 !important',
                    'background': '#ffffff',
                    'padding': '10px',
                    'word-wrap': 'break-word',
                    'border': '1px solid #cccccc',
                    'opacity': '1',
                    '-webkit-text-fill-color': '#000000'
                }
            ),
            visible=False,
            width=800,
            height=600,
            css_classes=['modal', 'modal-content'],
        )
        
        # Get references to modal buttons
        self.close_button = self.config_modal[0][2]
        self.config_text = self.config_modal[1]
        self.save_button = self.config_modal[2][0]
        self.cancel_button = self.config_modal[2][1]
        self.version_info = self.config_modal[3]
        
        # Initialize clustering and tracking
        self.clusterer = None
        self.tracker = None
        self.enable_clustering = self.config.clustering.enabled
        self.enable_tracking = self.config.tracking.enabled
        
        # Add timing variable
        self.last_update_time = None
        
        # Initialize plot data
        self.scatter_source = None
        self.cluster_source = ColumnDataSource({'x': [], 'y': [], 'size': [], 'cluster_id': []})
        self.track_source = ColumnDataSource({'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []})
        self.color_mapper = LinearColorMapper(palette=cc.rainbow, low=-1, high=1)
        
        # Initialize recording state
        self.is_recording = False
        self.recording_dir = "recordings"
        self.recorder = None
        
        # Add camera recorder
        self.camera_recorder = None
        
        # Set up callbacks
        self.load_config_button.param.watch(self._load_config_callback, 'value')
        self.connect_button.on_click(self._connect_callback)
        self.start_button.on_click(self._start_callback)
        self.stop_button.on_click(self._stop_callback)
        self.record_button.on_click(self._record_callback)
        self.exit_button.on_click(self._exit_callback)
        self.modify_params_checkbox.param.watch(self._toggle_params_panel, 'value')
        self.clutter_removal_checkbox.param.watch(self._clutter_removal_callback, 'value')
        self.frame_period_slider.param.watch(self._frame_period_callback, 'value_throttled')
        self.mob_enabled_checkbox.param.watch(self._mob_enabled_callback, 'value')
        self.mob_threshold_slider.param.watch(self._mob_threshold_callback, 'value_throttled')
        self.clustering_checkbox.param.watch(self._clustering_callback, 'value')
        self.tracking_checkbox.param.watch(self._tracking_callback, 'value')
        self.camera_autofocus.param.watch(self._camera_autofocus_callback, 'value')
        self.camera_focus.param.watch(self._camera_focus_callback, 'value')
        self.camera_button.on_click(self.start_camera)
        self.config_button.on_click(self._show_config_modal)
        self.close_button.on_click(self._hide_config_modal)
        self.cancel_button.on_click(self._hide_config_modal)
        self.save_button.on_click(self._save_config)
        
        self.start_button.disabled = True
        self.stop_button.disabled = True
        self.record_button.disabled = True
        
        # Create plot
        self.plot = self.create_plot()
        
        # Create layout
        self.layout = self.create_layout()
        
        # Initialize periodic callback (disabled by default)
        self.periodic_callback = None
        self.is_running = False
        
        # Set initial configuration text
        self.config_text.value = "# Connect to sensor to load profile"
    
    def _load_config_callback(self, event):
        """Handle loading of radar profile file."""
        if event.new:  # Check if a file was actually uploaded
            try:
                # Get the uploaded profile content
                profile_str = event.new.decode('utf-8')
                
                # Write to the default profile location, overwriting if it exists
                with open(self.config_file, 'w') as f:
                    f.write(profile_str)
                
                logger.info(f"Loaded radar profile: {self.config_file}")
                
            except Exception as e:
                logger.error(f"Error loading radar profile: {e}")
                # Don't reset config_file on error since we want to keep the default
    
    def _clutter_removal_callback(self, event):
        """Handle clutter removal checkbox changes."""
        if self.radar and self.radar.is_connected():
            self.radar.clutterRemoval = event.new
            logger.info(f"Clutter removal {'enabled' if event.new else 'disabled'}")
    
    def _connect_callback(self, event):
        """Handle connection to sensor."""
        try:
            self.connect_button.loading = True
            logger.info("Attempting to connect to sensor...")
            
            if not self._detect_radar_type():
                raise RadarConnectionError("No supported radar detected")
            
            logger.info(f"Creating {self.radar_type} radar instance")
            self.radar = create_radar()
            
            self.radar.connect(self.config_file)
            
            self.radar_data = RadarData(self.radar)
            
            if self.radar.version_info:
                formatted_info = '\n'.join(str(line) for line in self.radar.version_info)
                self.version_info.value = formatted_info
                
            if self.config_file:
                self.config_text.value = self.config_file
            
            if self.radar.is_connected():
                self.clutter_removal_checkbox.disabled = False
                self.frame_period_slider.disabled = False
                self.mob_enabled_checkbox.disabled = False
                
                try:
                    self.clutter_removal_checkbox.value = self.radar.clutterRemoval
                    self.frame_period_slider.value = self.radar.frame_period
                    self.mob_enabled_checkbox.value = self.radar.mob_enabled
                    self.mob_threshold_slider.value = self.radar.mob_threshold
                    self.mob_threshold_slider.disabled = not self.radar.mob_enabled
                except Exception as e:
                    logger.warning(f"Could not initialize all parameter values from radar: {e}")
            
            self.connect_button.loading = False
            self.connect_button.name = "Connected"
            self.connect_button.button_type = "success"
            self.start_button.disabled = False
            self.config_button.disabled = False
            self.connect_button.disabled = True
            
        except (RadarConnectionError, FileNotFoundError) as e:
            logger.error(f"Error connecting to sensor: {e}")
            self.connect_button.loading = False
            self.connect_button.name = "Connection Failed"
            self.connect_button.button_type = "danger"
            # Don't exit, just allow retry
            if self.radar:
                self.radar.close()
                self.radar = None
    
    def _record_callback(self, event):
        """Toggle recording state."""
        if not self.is_recording:
            os.makedirs(self.recording_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_filename = os.path.join(self.recording_dir, f"radar_data_{timestamp}")
            
            format_type = self.record_format_select.value.lower()
            
            clustering_params = {
                'eps': self.cluster_eps_slider.value,
                'min_samples': self.cluster_min_samples_slider.value
            }
            
            tracking_params = {
                'dt': self.frame_period_slider.value / 1000.0,  # Convert ms to seconds
                'max_distance': self.track_max_distance_slider.value,
                'min_hits': self.track_min_hits_slider.value,
                'max_misses': self.track_max_misses_slider.value
            }
            
            try:
                self.recorder = PointCloudRecorder(
                    base_filename,
                    format_type,
                    buffer_in_memory=(format_type == 'pcd'),  # Buffer in memory for PCD
                    enable_clustering=self.enable_clustering,
                    enable_tracking=self.enable_tracking,
                    clustering_params=clustering_params,
                    tracking_params=tracking_params
                )
                
                if self.camera_running and self.camera is not None:
                    cameras = {'main': self.camera}  # Use 'main' as ID for single camera
                    self.camera_recorder = CameraRecorder(self.recording_dir, cameras)
                    self.camera_recorder.start()
                
                self.is_recording = True
                self.record_button.param.update(
                    name='Stop Recording',
                    button_type='danger'
                )
                self.record_button.param.trigger('name')
                self.record_button.param.trigger('button_type')
                
                logger.info(f"Started recording to {base_filename}.{format_type}")
            except Exception as e:
                logger.error(f"Error starting recording: {e}")
                self.recorder = None
                if self.camera_recorder:
                    try:
                        self.camera_recorder.stop()
                    except Exception as ce:
                        logger.error(f"Error stopping camera recorder: {ce}")
                    self.camera_recorder = None
        else:
            # Stop recording
            if self.recorder:
                try:
                    self.recorder.close()
                except Exception as e:
                    logger.error(f"Error closing radar recorder: {e}")
                finally:
                    self.recorder = None
                    
            if self.camera_recorder:
                try:
                    self.camera_recorder.stop()
                except Exception as e:
                    logger.error(f"Error closing camera recorder: {e}")
                finally:
                    self.camera_recorder = None
                    
            self.is_recording = False
            self.record_button.param.update(
                name='Start Recording',
                button_type='primary'
            )
            self.record_button.param.trigger('name')
            self.record_button.param.trigger('button_type')
            
            logger.info("Stopped recording")
    
    def _start_callback(self, event):
        """
        Start periodic updates.
        
        This method starts the radar data acquisition and visualization
        when the user clicks the Start button.
        
        Parameters
        ----------
        event : param.Event
            The button click event
            
        Returns
        -------
        None
        """
        if not self.is_running and self.radar.is_connected():
            self.stop_button.disabled = False
            self.record_button.disabled = False
            self.radar.configure_and_start()

            if self.radar.clutterRemoval:
                self.clutter_removal_checkbox.value = True
                
            if self.radar.mob_enabled:
                self.mob_enabled_checkbox.value = True
                self.mob_threshold_slider.value = self.radar.mob_threshold
            
            # Create a new RadarData instance for the running radar
            self.radar_data = RadarData(self.radar)
            
            if self.clustering_checkbox.value:
                self.enable_clustering = True
                self.clusterer = PointCloudClustering(
                    eps=self.cluster_eps_slider.value,
                    min_samples=self.cluster_min_samples_slider.value
                )
                
                if self.tracking_checkbox.value:
                    self.enable_tracking = True
                    self.tracker = PointCloudTracker(
                        dt=self.frame_period_slider.value / 1000.0,  # Convert ms to seconds
                        max_distance=self.track_max_distance_slider.value,
                        min_hits=self.track_min_hits_slider.value,
                        max_misses=self.track_max_misses_slider.value
                    )
            
            self._save_current_config()
            
            # Instead of periodic callback, schedule the first update
            self.is_running = True
            pn.state.onload(self.update_plot)
            self.start_button.button_type = 'success'
            self.start_button.name = 'Running'
            self.start_button.disabled = True
    
    def _stop_callback(self, event):
        """Stop periodic updates."""
        if self.is_running:
            self.start_button.disabled = False
            self.stop_button.disabled = True
            if self.radar.is_connected():
                logger.info("Stopping sensor...")
                self.radar.stop()
            self.is_running = False
            self.start_button.button_type = 'primary'
            self.start_button.name = 'Start'
            # Also stop recording if it's active
            if self.is_recording:
                self._record_callback(None)
            self.record_button.disabled = True
    
    def _exit_callback(self, event):
        """Handle exit button click - cleanup and quit."""
        logger.info("Cleaning up and exiting...")
        self.cleanup()
        # Stop the server more gracefully
        if pn.state.curdoc:
            pn.state.curdoc.remove_root(self.layout)
        os._exit(0)
    
    def _show_config_modal(self, event):
        """Show the sensor profile modal."""
        self.config_modal.visible = True

    def _hide_config_modal(self, event):
        """Hide the sensor profile modal."""
        self.config_modal.visible = False

    def _save_config(self, event):
        """Save the radar profile and hide modal."""
        try:
            with open(self.config_file, 'w') as f:
                f.write(self.config_text.value)
                
            if self.radar.is_connected():
                responses = self.radar.send_profile(self.config_text.value)
                if responses:
                    logger.info("Sensor responses:")
                    for response in responses:
                        logger.info(f"  {response}")
                
            logger.info("Radar profile saved successfully")
            self._hide_config_modal(None)
            
        except Exception as e:
            logger.error(f"Error saving radar profile: {e}")

    def create_plot(self):
        """
        Create the radar point cloud visualization plot.
        
        This method initializes the Bokeh figure for visualizing radar data,
        including point cloud, clusters, and tracks.
        
        Returns
        -------
        pn.pane.Bokeh
            Panel pane containing the Bokeh figure
            
        Notes
        -----
        The plot includes:
        - Scatter plot for radar points, colored by velocity
        - Circle glyphs for cluster centers
        - Labels and segments for tracks and their velocity vectors
        - A color bar for the velocity scale
        """
        p = figure(
            title='Radar Point Cloud', 
            width=self.config.display.plot_width,
            height=self.config.display.plot_height,
            x_range=self.config.display.x_range,
            y_range=self.config.display.y_range,
            tools='pan,wheel_zoom,box_zoom,reset,save',
            toolbar_location='above'
        )
        
        self.data_source = ColumnDataSource({
            'x': [], 
            'y': [], 
            'velocity': [], 
            'size': []
        })
        
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
        
        # Add cluster centers visualization
        p.circle(
            x='x',
            y='y',
            size='size',
            color='red',
            alpha=0.5,
            line_width=2,
            source=self.cluster_source,
            name='clusters'
        )
        
        # Add track IDs visualization
        labels = LabelSet(
            x='x',
            y='y',
            text='track_id',
            text_font_size='10pt',
            text_color='blue',
            source=self.track_source,
            name='track_labels'
        )
        p.add_layout(labels)
        
        # Add velocity vectors for tracks
        p.segment(
            x0='x',
            y0='y',
            x1='vx',
            y1='vy',
            color='blue',
            line_width=2,
            source=self.track_source,
            name='track_vectors'
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
        
        # Enable grid lines for better readability
        p.grid.grid_line_alpha = 0.3
        
        return pn.pane.Bokeh(p)
    
    def update_plot(self):
        """
        Update the plot with new radar data.
        
        This method retrieves the next point cloud from the radar,
        processes it and updates the visualization. It handles clustering
        and tracking if enabled, and records data if recording is active.
        
        The method is called periodically when the radar is running.
        
        Returns
        -------
        None
        
        Notes
        -----
        This method schedules itself to run again if the radar is still running.
        """
        if not self.is_running or self.radar_data is None:
            return
            
        try:
            point_cloud = next(iter(self.radar_data))
            
            empty_data = {'x': [], 'y': [], 'velocity': [], 'size': []}
            empty_cluster_data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
            empty_track_data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            
            if point_cloud.num_points == 0:
                self.data_source.data = empty_data
                self.cluster_source.data = empty_cluster_data
                self.track_source.data = empty_track_data
                
                if self.is_running:
                    pn.state.add_periodic_callback(self.update_plot, period=10, count=1)
                return
                
            try:
                x, y, z = point_cloud.to_cartesian()
                
                x_range = self.config.display.x_range
                y_range = self.config.display.y_range
                x = np.clip(x, x_range[0], x_range[1])
                y = np.clip(y, y_range[0], y_range[1])
                
                velocity = np.clip(point_cloud.velocity, -1, 1)
                
                if hasattr(point_cloud, 'snr') and point_cloud.snr is not None and len(point_cloud.snr) > 0:
                    snr_values = point_cloud.snr
                else:
                    snr_values = np.ones(point_cloud.num_points) * 30  # Default to mid-range if no SNR
                
                point_sizes = 5 + np.clip(snr_values / 60.0, 0, 1) * 15  # Scale to range 5-20 pixels
                
                # Ensure all arrays have the same length before updating
                min_length = min(len(x), len(y), len(velocity), len(point_sizes))
                
                self.data_source.data = {
                    'x': x[:min_length],
                    'y': y[:min_length],
                    'velocity': velocity[:min_length],
                    'size': point_sizes[:min_length]
                }
                
                self._process_clustering_tracking(point_cloud)
                
                if self.is_recording and self.recorder:
                    try:
                        frame_number = point_cloud.metadata.get('frame_number', 0)
                        self.recorder.add_frame(point_cloud, frame_number)
                    except Exception as e:
                        logger.error(f"Error recording frame: {e}")
            except Exception as e:
                logger.error(f"Error processing point cloud: {e}")
                self.data_source.data = empty_data
                self.cluster_source.data = empty_cluster_data
                self.track_source.data = empty_track_data

            if self.is_running:
                pn.state.add_periodic_callback(self.update_plot, period=10, count=1)

        except StopIteration:
            logger.warning("No more radar data available")
            self._stop_callback(None)
        except Exception as e:
            logger.error(f"Error updating plot: {e}")
            self.data_source.data = {'x': [], 'y': [], 'velocity': [], 'size': []}
            self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            self._stop_callback(None)
    
    def _process_clustering_tracking(self, point_cloud):
        """
        Process clustering and tracking for a point cloud.
        
        This helper method performs clustering and tracking on the 
        provided point cloud if these features are enabled.
        
        Parameters
        ----------
        point_cloud : RadarPointCloud
            The radar point cloud to process
            
        Returns
        -------
        None
        """
        if not (self.enable_clustering and self.clusterer is not None):
            self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            return
            
        clusters = self.clusterer.cluster(point_cloud)
        
        if not clusters:
            self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            return
            
        cluster_x = []
        cluster_y = []
        cluster_sizes = []
        cluster_ids = []
        
        for i, cluster in enumerate(clusters):
            cluster_x.append(cluster.centroid[0])
            cluster_y.append(cluster.centroid[1])
            cluster_sizes.append(30 + cluster.num_points * 2)  # Size based on number of points
            cluster_ids.append(str(i))
        
        self.cluster_source.data = {
            'x': cluster_x,
            'y': cluster_y,
            'size': cluster_sizes,
            'cluster_id': cluster_ids
        }
        
        if not (self.enable_tracking and self.tracker is not None):
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            return
            
        tracks = self.tracker.update(clusters)
        
        if not tracks:
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            return
            
        track_x = []
        track_y = []
        track_ids = []
        track_vx = []
        track_vy = []
        
        vel_scale = 0.5
        
        for track in tracks:
            track_x.append(track.state[0])
            track_y.append(track.state[1])
            track_ids.append(str(track.track_id))
            
            vx = track.state[0] + track.state[3] * vel_scale
            vy = track.state[1] + track.state[4] * vel_scale
            track_vx.append(vx)
            track_vy.append(vy)
        
        self.track_source.data = {
            'x': track_x,
            'y': track_y,
            'track_id': track_ids,
            'vx': track_vx,
            'vy': track_vy
        }

    def create_layout(self):
        """Create the GUI layout."""
        # Create a header
        header = pn.pane.Markdown('# Radar Sensor Control Panel', 
                                styles={'background': '#f0f0f0', 'padding': '10px'})
        
        # Create a sidebar with controls
        sidebar = pn.Column(
            pn.pane.Markdown('## Controls'),
            pn.Row(self.load_config_button),
            self.connect_button,  # Connect button first
            self.config_button,   # Config button second
            pn.layout.Divider(),
            pn.pane.Markdown('## Camera'),
            pn.Row(
                self.camera_select,
                self.camera_button
            ),
            pn.layout.Divider(),
            self.start_button,
            self.stop_button,
            pn.layout.Divider(),
            pn.pane.Markdown('## Recording'),
            self.record_format_select,
            self.record_button,
            pn.layout.Divider(),
            self.exit_button,     # Moved exit button up
            pn.layout.Divider(),
            self.modify_params_checkbox,  # Moved modify parameters checkbox down
            width=300,  # Reverted to 300 pixels for better usability
            styles={'background': '#f8f8f8', 'padding': '10px'}
        )
        
        # Create main content area with side-by-side plots
        main = pn.Column(
            pn.pane.Markdown('## Real-time Data'),
            pn.Row(
                self.plot,
                self.create_camera_plot(),
            ),
            self.config_modal,  # Add the modal to main layout
            self.params_panel,  # Add the parameters panel to main layout
            styles={'padding': '10px'},
            max_width=2000  # Increased max width to accommodate both plots
        )
        
        # Add CSS for modal and panel styling
        pn.extension(raw_css=["""
        .modal {
            position: fixed !important;
            top: 50% !important;
            left: 50% !important;
            transform: translate(-50%, -50%) !important;
            z-index: 1000 !important;
        }
        .modal-content {
            background: white !important;
            border: 1px solid #ddd !important;
            border-radius: 5px !important;
            padding: 20px !important;
            box-shadow: 0 0 10px rgba(0,0,0,0.1) !important;
        }
        .bk-root .bk-float-panel {
            position: fixed !important;
            top: 80px !important;
            right: 20px !important;
            z-index: 1000 !important;
        }
        .bk-root .bk-sidebar {
            width: 300px !important;
            min-width: 300px !important;
            max-width: 300px !important;
        }
        """])
        
        # Combine everything into a template
        template = pn.template.MaterialTemplate(
            title='XWR68XX ISK Radar GUI',
            sidebar=sidebar,
            main=main,
            header=header,
            sidebar_width=300  # Reverted back to 300 pixels for better usability
        )
        
        return template
    
    def cleanup(self):
        """
        Clean up resources when closing the GUI.
        
        This method ensures all resources are properly released when
        the application is closing. It:
        1. Stops radar if running
        2. Stops recording if active
        3. Closes radar connection
        4. Stops camera if running
        5. Saves final configuration
        
        Returns
        -------
        None
        
        Notes
        -----
        This method is designed to be robust, handling exceptions for
        each cleanup step independently to ensure maximum cleanup success.
        """
        logger.info("Performing cleanup...")
        
        if self.is_running:
            try:
                logger.info("Stopping radar...")
                self._stop_callback(None)
            except Exception as e:
                logger.error(f"Error stopping radar during cleanup: {e}")
        
        if self.is_recording:
            try:
                logger.info("Stopping recording...")
                if self.recorder:
                    try:
                        self.recorder.close()
                        logger.info("Radar recorder closed successfully")
                    except Exception as e:
                        logger.error(f"Error closing radar recorder during cleanup: {e}")
                    finally:
                        self.recorder = None
                
                if self.camera_recorder:
                    try:
                        self.camera_recorder.stop()
                        logger.info("Camera recorder closed successfully")
                    except Exception as e:
                        logger.error(f"Error closing camera recorder during cleanup: {e}")
                    finally:
                        self.camera_recorder = None
            except Exception as e:
                logger.error(f"Error stopping recording during cleanup: {e}")
        
        if self.radar is not None:
            try:
                if self.radar.is_connected():
                    logger.info("Closing radar connection...")
                    self.radar.close()
            except Exception as e:
                logger.error(f"Error closing radar connection during cleanup: {e}")
            finally:
                self.radar = None
        
        if self.camera_running:
            try:
                logger.info("Stopping camera...")
                self.stop_camera()
            except Exception as e:
                logger.error(f"Error stopping camera during cleanup: {e}")
        
        try:
            logger.info("Saving configuration...")
            self._save_current_config()
        except Exception as e:
            logger.error(f"Error saving configuration during cleanup: {e}")
            
        logger.info("Cleanup completed")

    def _detect_radar_type(self):
        """Auto-detect which radar is connected."""
        # Check serial ports and identify device type
        radar_base = RadarConnection()
        self.radar_type = radar_base.detect_radar_type()
        return self.radar_type is not None

    def _toggle_params_panel(self, event):
        """Toggle the visibility of the parameters panel."""
        self.params_panel.visible = event.new
    
    def _frame_period_callback(self, event):
        """Handle frame period slider changes."""
        if self.radar and self.radar.is_connected():
            try:
                self.radar.set_frame_period(event.new)
                logger.info(f"Frame period set to {event.new}ms")
            except Exception as e:
                logger.error(f"Error setting frame period: {e}")
    
    def _mob_enabled_callback(self, event):
        """Handle multi-object beamforming enable/disable."""
        if self.radar and self.radar.is_connected():
            try:
                self.radar.set_mob_enabled(event.new)
                logger.info(f"Multi-object beamforming {'enabled' if event.new else 'disabled'}")
                # Only enable threshold slider if MOB is enabled
                self.mob_threshold_slider.disabled = not event.new
            except Exception as e:
                logger.error(f"Error setting MOB state: {e}")
    
    def _mob_threshold_callback(self, event):
        """Handle multi-object beamforming threshold changes."""
        if self.radar and self.radar.is_connected():
            try:
                self.radar.set_mob_threshold(event.new)
                logger.info(f"MOB threshold set to {event.new}")
            except Exception as e:
                logger.error(f"Error setting MOB threshold: {e}")

    def _clustering_callback(self, event):
        """Handle clustering checkbox changes."""
        if self.radar and self.radar.is_connected():
            self.enable_clustering = event.new
            logger.info(f"Clustering {'enabled' if event.new else 'disabled'}")
            # Update configuration
            self._save_current_config()
            # Enable/disable related controls
            self.cluster_eps_slider.disabled = not event.new
            self.cluster_min_samples_slider.disabled = not event.new
            self.tracking_checkbox.disabled = not event.new
    
    def _tracking_callback(self, event):
        """Handle tracking checkbox changes."""
        if self.radar and self.radar.is_connected():
            self.enable_tracking = event.new
            logger.info(f"Tracking {'enabled' if event.new else 'disabled'}")
            # Update configuration
            self._save_current_config()
            # Enable/disable related controls
            self.track_max_distance_slider.disabled = not event.new
            self.track_min_hits_slider.disabled = not event.new
            self.track_max_misses_slider.disabled = not event.new

    def _save_current_config(self):
        """Save current GUI state to configuration."""
        updates = {
            'processing': {
                'clutter_removal': self.clutter_removal_checkbox.value,
                'mob_enabled': self.mob_enabled_checkbox.value,
                'mob_threshold': self.mob_threshold_slider.value,
                'frame_period_ms': self.frame_period_slider.value
            },
            'clustering': {
                'enabled': self.clustering_checkbox.value,
                'eps': self.cluster_eps_slider.value,
                'min_samples': self.cluster_min_samples_slider.value
            },
            'tracking': {
                'enabled': self.tracking_checkbox.value,
                'max_distance': self.track_max_distance_slider.value,
                'min_hits': self.track_min_hits_slider.value,
                'max_misses': self.track_max_misses_slider.value,
                'dt': self.frame_period_slider.value / 1000.0
            }
        }
        try:
            self.config = self.config_manager.update_config(updates)
            self.config_manager.save_config()
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def create_camera_plot(self):
        """
        Create the camera display plot.
        
        This method initializes the Bokeh figure for displaying
        the camera feed alongside the radar visualization.
        
        Returns
        -------
        pn.pane.Bokeh
            Panel pane containing the Bokeh figure for camera display
            
        Notes
        -----
        The camera plot has no axes or grid lines, just the camera image.
        """
        p = figure(
            title='Camera View',
            width=640,
            height=480,
            x_range=(0, 640),
            y_range=(0, 480),
            tools='',
            toolbar_location=None
        )
        
        self.camera_source = ColumnDataSource({'image': [], 'dw': [], 'dh': []})
        
        self.camera_plot = p.image_rgba(
            image='image',
            x=0,
            y=0,
            dw='dw',
            dh='dh',
            source=self.camera_source,
            name='camera_image'
        )
        
        p.axis.visible = False
        p.grid.visible = False
        p.min_border = 0
        
        return pn.pane.Bokeh(p)

    def start_camera(self, event):
        """
        Start or stop the camera stream.
        
        This method toggles the camera on/off. When starting, it initializes
        the camera with the selected device ID and sets up the periodic callback
        for updating the display.
        
        Parameters
        ----------
        event : param.Event
            The button click event
            
        Returns
        -------
        None
        """
        if not self.camera_running:
            try:
                device_id = int(self.camera_select.value)
                # get camera name from config
                camera_name = self.config.get('camera', {}).get('implementation', 'Picamera')
                self.camera = BaseCamera.create_camera(camera_name, device_id=device_id)
                self.camera.start()
                self.camera_running = True
                
                self.camera_button.name = 'Stop Camera'
                self.camera_button.button_type = 'danger'
                
                if self.camera._cap:
                    is_autofocus = bool(self.camera._cap.get(self.camera.cv2.CAP_PROP_AUTOFOCUS))
                    self.camera_autofocus.value = is_autofocus
                    self.camera_focus.disabled = is_autofocus
                    
                    if not is_autofocus:
                        focus_value = int(self.camera._cap.get(self.camera.cv2.CAP_PROP_FOCUS))
                        self.camera_focus.value = focus_value
                
                if hasattr(self, 'camera_callback') and self.camera_callback is not None:
                    self.camera_callback.stop()
                    
                self.camera_callback = pn.state.add_periodic_callback(
                    self.update_camera,
                    period=33  # ~30 FPS
                )
                logger.info(f"Started camera {device_id}")
                
            except Exception as e:
                logger.error(f"Error starting camera: {e}")
                if self.camera:
                    self.camera.stop()
                    self.camera = None
                self.camera_running = False
        else:
            self.stop_camera()

    def stop_camera(self, event=None):
        """
        Stop the camera stream.
        
        This method stops the camera stream, cleans up resources,
        and updates the UI accordingly.
        
        Parameters
        ----------
        event : param.Event, optional
            The button click event, if called from button
            
        Returns
        -------
        None
        """
        if not self.camera_running:
            return
            
        self.camera_running = False
        
        if hasattr(self, 'camera_callback') and self.camera_callback is not None:
            try:
                self.camera_callback.stop()
            except Exception as e:
                logger.error(f"Error stopping camera callback: {e}")
            finally:
                self.camera_callback = None
                
        if self.camera:
            try:
                self.camera.stop()
            except Exception as e:
                logger.error(f"Error stopping camera: {e}")
            finally:
                self.camera = None
                
        self.camera_button.name = 'Start Camera'
        self.camera_button.button_type = 'primary'
        
        if len(self.camera_source.data['image']) > 0:
            self.camera_source.data.update({'image': [], 'dw': [], 'dh': []})
        
        logger.info("Stopped camera")

    def update_camera(self):
        """
        Update the camera display.
        
        This method retrieves the next frame from the camera
        and updates the display. If recording is active, the frame
        is also recorded.
        
        Returns
        -------
        None
        
        Notes
        -----
        This method is called periodically when the camera is running.
        It skips frames if the camera is falling behind to maintain performance.
        """
        if not self.camera_running or self.camera is None:
            return
        
        try:
            frames_behind = self.camera._cap.get(self.camera.cv2.CAP_PROP_POS_FRAMES)
            if frames_behind > 0:
                for _ in range(int(frames_behind) - 1):
                    if self.camera_running:
                        self.camera._cap.grab()
                    else:
                        return
            
            frame_data = next(self.camera)
            if frame_data is None:
                return
                
            frame = self.camera.cv2.cvtColor(frame_data['image'], self.camera.cv2.COLOR_BGR2RGBA).view(np.uint32).reshape(frame_data['image'].shape[:-1])
            
            current_images = self.camera_source.data['image']
            if len(current_images) == 0 or not np.array_equal(current_images[0], frame):
                self.camera_source.data.update({
                    'image': [frame],
                    'dw': [frame_data['width']],
                    'dh': [frame_data['height']]
                })
            
            if not self.camera_autofocus.value:
                current_focus = int(self.camera._cap.get(self.camera.cv2.CAP_PROP_FOCUS))
                if abs(current_focus - self.camera_focus.value) > 0:
                    self.camera_focus.value = current_focus
            
        except StopIteration:
            logger.warning("Camera stream ended")
            self.stop_camera()
        except Exception as e:
            logger.error(f"Error updating camera: {e}")
            self.stop_camera()

    def _camera_autofocus_callback(self, event):
        """Handle camera autofocus checkbox changes."""
        if self.camera and self.camera_running:
            try:
                if not event.new:  # Autofocus disabled
                    self.camera._cap.set(self.camera.cv2.CAP_PROP_AUTOFOCUS, 0)
                    self.camera_focus.disabled = False
                    # Get current focus value
                    current_focus = int(self.camera._cap.get(self.camera.cv2.CAP_PROP_FOCUS))
                    self.camera_focus.value = current_focus
                else:  # Autofocus enabled
                    self.camera._cap.set(self.camera.cv2.CAP_PROP_AUTOFOCUS, 1)
                    self.camera_focus.disabled = True
                logger.info(f"Camera autofocus {'enabled' if event.new else 'disabled'}")
            except Exception as e:
                logger.error(f"Error setting camera autofocus: {e}")

    def _camera_focus_callback(self, event):
        """Handle camera focus slider changes."""
        if self.camera and self.camera_running and not self.camera_autofocus.value:
            try:
                self.camera._cap.set(self.camera.cv2.CAP_PROP_FOCUS, event.new)
                logger.info(f"Camera focus set to {event.new}")
            except Exception as e:
                logger.error(f"Error setting camera focus: {e}")
