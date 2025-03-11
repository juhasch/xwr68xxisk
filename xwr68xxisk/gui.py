"""Simple Bokeh GUI for the xwr68xxisk radar sensor evaluation kit."""

import numpy as np
import panel as pn
import holoviews as hv
from bokeh.plotting import figure
from bokeh.models import ColorBar, LinearColorMapper, ColumnDataSource, LabelSet
import colorcet as cc
from xwr68xxisk.radar import RadarConnectionError
from xwr68xxisk.parse import RadarData
from xwr68xxisk.point_cloud import RadarPointCloud
from xwr68xxisk.clustering import PointCloudClustering
from xwr68xxisk.tracking import PointCloudTracker
import os
import logging
from datetime import datetime
from panel.widgets import TextAreaInput, Button
from xwr68xxisk.radar import RadarConnection, create_radar

logger = logging.getLogger(__name__)

# Initialize extensions (fix order and syntax)
hv.extension('bokeh')
pn.extension(design="material", sizing_mode="stretch_width")


class RadarGUI:
    def __init__(self):
        # Initialize radar connection
        # Note: Actual connection to the physical device happens later via connect() method
        self.radar = None
        self.radar_type = None  # Will be set during connection
        self.radar_data = None  # Will hold the RadarData instance
        
        # Initialize clustering and tracking
        self.clusterer = None
        self.tracker = None
        self.enable_clustering = False
        self.enable_tracking = False
        
        # Load default configuration - will be set when radar type is detected
        self.config_file = None
        
        # Add timing variable
        self.last_update_time = None
        
        # Initialize plot data
        self.scatter_source = None
        self.cluster_source = ColumnDataSource({'x': [], 'y': [], 'size': [], 'cluster_id': []})
        self.track_source = ColumnDataSource({'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []})
        self.color_mapper = LinearColorMapper(palette=cc.rainbow, low=-1, high=1)
        
        # Recording state
        self.is_recording = False
        self.recording_dir = "recordings"
        self.recording_file = None
        
        # Create controls
        self.load_config_button = pn.widgets.FileInput(name='Load Config', accept='.cfg')
        self.connect_button = pn.widgets.Button(name='Connect to Sensor', button_type='primary')
        self.start_button = pn.widgets.Button(name='Start', button_type='primary')
        self.stop_button = pn.widgets.Button(name='Stop', button_type='danger')
        self.record_button = pn.widgets.Button(name='Start Recording', button_type='primary')
        self.exit_button = pn.widgets.Button(name='Exit', button_type='danger')
        
        # Parameters panel controls
        self.modify_params_checkbox = pn.widgets.Checkbox(name='Modify Parameters', value=False)
        self.clutter_removal_checkbox = pn.widgets.Checkbox(name='Static Clutter Removal', value=False)
        self.frame_period_slider = pn.widgets.FloatSlider(name='Frame Period (ms)', start=50, end=1000, value=100, step=10)
        self.mob_enabled_checkbox = pn.widgets.Checkbox(name='Multi-object Beamforming', value=False)
        self.mob_threshold_slider = pn.widgets.FloatSlider(name='MOB Threshold', start=0, end=1, value=0.5, step=0.01)
        
        # Add clustering and tracking controls
        self.clustering_checkbox = pn.widgets.Checkbox(name='Enable Clustering', value=False)
        self.tracking_checkbox = pn.widgets.Checkbox(name='Enable Tracking', value=False)
        self.cluster_eps_slider = pn.widgets.FloatSlider(name='Cluster Size (m)', start=0.1, end=2.0, value=0.5, step=0.1)
        self.cluster_min_samples_slider = pn.widgets.IntSlider(name='Min Points per Cluster', start=3, end=20, value=5, step=1)
        self.track_max_distance_slider = pn.widgets.FloatSlider(name='Max Track Distance (m)', start=0.5, end=5.0, value=2.0, step=0.1)
        self.track_min_hits_slider = pn.widgets.IntSlider(name='Min Track Hits', start=2, end=10, value=3, step=1)
        self.track_max_misses_slider = pn.widgets.IntSlider(name='Max Track Misses', start=2, end=10, value=5, step=1)
        
        # Create floating panel for parameters
        self.params_panel = pn.layout.FloatPanel(
            pn.Column(
                self.clutter_removal_checkbox,
                self.frame_period_slider,
                self.mob_enabled_checkbox,
                self.mob_threshold_slider,
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
        
        # Set up callbacks
        self.load_config_button.param.watch(self._load_config_callback, 'value')
        self.connect_button.on_click(self._connect_callback)
        self.start_button.on_click(self._start_callback)
        self.stop_button.on_click(self._stop_callback)
        self.record_button.on_click(self._record_callback)
        self.exit_button.on_click(self._exit_callback)
        self.modify_params_checkbox.param.watch(self._toggle_params_panel, 'value')
        self.clutter_removal_checkbox.param.watch(self._clutter_removal_callback, 'value')
        self.frame_period_slider.param.watch(self._frame_period_callback, 'value')
        self.mob_enabled_checkbox.param.watch(self._mob_enabled_callback, 'value')
        self.mob_threshold_slider.param.watch(self._mob_threshold_callback, 'value')
        self.clustering_checkbox.param.watch(self._clustering_callback, 'value')
        self.tracking_checkbox.param.watch(self._tracking_callback, 'value')
        
        self.start_button.disabled = True
        self.stop_button.disabled = True
        self.record_button.disabled = True
        
        # Create plot
        self.plot = self.create_plot()
        
        # Add configuration modal components
        self.config_modal = pn.Column(
            pn.Row(
                pn.pane.Markdown('## Sensor Configuration'),
                pn.layout.HSpacer(),
                pn.widgets.Button(name='✕', width=30, align='end'),
                sizing_mode='stretch_width'
            ),
            TextAreaInput(
                name="Configuration",
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
        
        # Add configuration button to open modal
        self.config_button = Button(
            name="Configure Sensor",
            button_type="primary",
            disabled=True  # Initially disabled until connected
        )
        
        # Get references to modal buttons
        self.close_button = self.config_modal[0][2]
        self.config_text = self.config_modal[1]
        self.save_button = self.config_modal[2][0]
        self.cancel_button = self.config_modal[2][1]
        self.version_info = self.config_modal[3]
        
        # Set up callbacks
        self.config_button.on_click(self._show_config_modal)
        self.close_button.on_click(self._hide_config_modal)
        self.cancel_button.on_click(self._hide_config_modal)
        self.save_button.on_click(self._save_config)
        
        # Create layout
        self.layout = self.create_layout()
        
        # Initialize periodic callback (disabled by default)
        self.periodic_callback = None
        self.is_running = False
        
        # Set initial configuration text
        self.config_text.value = "# Connect to sensor to load configuration"
    
    def _load_config_callback(self, event):
        """Handle loading of configuration file."""
        if event.new:  # Check if a file was actually uploaded
            self.config_file = event.new.decode('utf-8')
            logger.info("Loaded configuration file")
    
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
            
            # Auto-detect radar type
            if not self._detect_radar_type():
                raise RadarConnectionError("No supported radar detected")
            
            logger.info(f"Creating {self.radar_type} radar instance")
            self.radar = create_radar(self.radar_type)
            
            # Now connect with the appropriate configuration
            self.radar.connect(self.config_file)
            
            # Create RadarData instance for the connected radar
            self.radar_data = RadarData(self.radar)
            
            # Update version info in the modal
            if self.radar.version_info:
                formatted_info = '\n'.join(str(line) for line in self.radar.version_info)
                self.version_info.value = formatted_info
                
            # Set the configuration text directly
            if self.config_file:
                self.config_text.value = self.config_file
            
            # Initialize parameter controls with current radar settings
            if self.radar.is_connected():
                # Enable all parameter controls
                self.clutter_removal_checkbox.disabled = False
                self.frame_period_slider.disabled = False
                self.mob_enabled_checkbox.disabled = False
                # MOB threshold is only enabled if MOB is enabled
                self.mob_threshold_slider.disabled = not self.mob_enabled_checkbox.value
                
                # Set initial values from radar if available
                try:
                    self.clutter_removal_checkbox.value = self.radar.clutterRemoval
                    self.frame_period_slider.value = self.radar.frame_period
                    self.mob_enabled_checkbox.value = self.radar.mob_enabled
                    self.mob_threshold_slider.value = self.radar.mob_threshold
                except Exception as e:
                    logger.warning(f"Could not initialize all parameter values: {e}")
            
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
            # Start recording
            os.makedirs(self.recording_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join(self.recording_dir, f"radar_data_{timestamp}.csv")
            self.recording_file = open(filename, "w")
            # Write header with more comprehensive fields
            self.recording_file.write("frame,x,y,z,velocity,range,azimuth,elevation,snr\n")
            self.is_recording = True
            self.record_button.name = 'Stop Recording'
            self.record_button.button_type = 'danger'
            logger.info(f"Started recording to {filename}")
        else:
            # Stop recording
            if self.recording_file:
                self.recording_file.close()
                self.recording_file = None
            self.is_recording = False
            self.record_button.name = 'Start Recording'
            self.record_button.button_type = 'primary'
            logger.info("Stopped recording")
    
    def _start_callback(self, event):
        """Start periodic updates."""
        if not self.is_running and self.radar.is_connected():
            self.stop_button.disabled = False
            self.record_button.disabled = False
            self.radar.configure_and_start()
            
            # Create a new RadarData instance for the running radar
            self.radar_data = RadarData(self.radar)
            
            # Initialize clustering and tracking if enabled
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
        # Force exit the program
        os._exit(0)
    
    def _load_initial_config(self):
        """Load the initial configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config_text.value = f.read()
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.config_text.value = "# Error loading configuration file"

    def _show_config_modal(self, event):
        """Show the configuration modal."""
        self.config_modal.visible = True

    def _hide_config_modal(self, event):
        """Hide the configuration modal."""
        self.config_modal.visible = False

    def _save_config(self, event):
        """Save the configuration and hide modal."""
        try:
            # Save to file
            with open(self.config_file, 'w') as f:
                f.write(self.config_text.value)
                
            # If connected, send configuration to sensor
            if self.radar.is_connected():
                responses = self.radar.send_config(self.config_text.value)
                if responses:
                    logger.info("Sensor responses:")
                    for response in responses:
                        logger.info(f"  {response}")
                
            logger.info("Configuration saved successfully")
            self._hide_config_modal(None)
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def create_plot(self):
        """Create the scatter plot."""
        p = figure(
            title='Radar Point Cloud', 
            width=1100,     # Reduced from 1200 to better fit MacBook screens
            height=600,    # Reduced from 800 to better fit MacBook screens
            x_range=(-2.5, 2.5),  # Set fixed x range to ±5m
            y_range=(0, 5)   # Set fixed y range to ±5m
        )
        
        # Set up the scatter plot with empty data source
        self.data_source = ColumnDataSource({
            'x': [], 
            'y': [], 
            'velocity': [], 
            'size': []
        })
        
        # Set up the scatter plot
        self.scatter_source = p.scatter(
            x='x',
            y='y', 
            size='size',
            fill_color={'field': 'velocity', 'transform': self.color_mapper},
            line_color=None,
            alpha=0.6,
            source=self.data_source
        )
        
        # Add cluster centers
        p.circle(
            x='x',
            y='y',
            size='size',
            color='red',
            alpha=0.5,
            line_width=2,
            source=self.cluster_source
        )
        
        # Add track IDs
        labels = LabelSet(
            x='x',
            y='y',
            text='track_id',
            text_font_size='10pt',
            text_color='blue',
            source=self.track_source
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
            source=self.track_source
        )
        
        # Add colorbar
        color_bar = ColorBar(
            color_mapper=self.color_mapper,
            title='Velocity (m/s)',
            location=(0, 0)
        )
        p.add_layout(color_bar, 'right')
        
        # Set up axes
        p.axis.axis_label_text_font_size = '12pt'
        p.axis.axis_label_text_font_style = 'normal'
        p.xaxis.axis_label = 'X Position (m)'
        p.yaxis.axis_label = 'Y Position (m)'
        
        return pn.pane.Bokeh(p)
    
    def update_plot(self):
        """Update the plot with new radar data using RadarPointCloud."""
        
        try:
            # Get point cloud using the new iterator functionality
            if self.radar_data is not None:
                # Get the next point cloud from the iterator
                point_cloud = next(iter(self.radar_data))
                
                if point_cloud.num_points > 0:
                    # Get Cartesian coordinates
                    x, y, z = point_cloud.to_cartesian()
                    
                    # Clip x and y values to plot range
                    x = np.clip(x, -2.5, 2.5)
                    y = np.clip(y, 0, 5)
                    
                    # Clip velocity to color mapper range
                    velocity = np.clip(point_cloud.velocity, -1, 1)
                    
                    # Get SNR values for point sizing
                    if point_cloud.snr is not None and len(point_cloud.snr) > 0:
                        snr_values = point_cloud.snr
                    else:
                        snr_values = np.ones(point_cloud.num_points) * 30  # Default to mid-range if no SNR
                    
                    # Scale and clip SNR only for display
                    display_sizes = np.clip(snr_values / 60.0, 0, 1)  # Normalize to 0-1 range
                    point_sizes = 5 + display_sizes * 15  # Scale to range 5-20 pixels
                    
                    # Ensure all arrays have the same length before updating
                    min_length = min(len(x), len(y), len(velocity), len(point_sizes))
                    
                    # Update the scatter plot data with consistent lengths
                    self.data_source.data = {
                        'x': x[:min_length],
                        'y': y[:min_length],
                        'velocity': velocity[:min_length],
                        'size': point_sizes[:min_length]
                    }
                    
                    # Perform clustering if enabled
                    if self.enable_clustering and self.clusterer is not None:
                        clusters = self.clusterer.cluster(point_cloud)
                        
                        if clusters:
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
                            
                            # Perform tracking if enabled
                            if self.enable_tracking and self.tracker is not None:
                                tracks = self.tracker.update(clusters)
                                
                                if tracks:
                                    track_x = []
                                    track_y = []
                                    track_ids = []
                                    track_vx = []  # End points for velocity vectors
                                    track_vy = []
                                    
                                    for track in tracks:
                                        track_x.append(track.state[0])  # x position
                                        track_y.append(track.state[1])  # y position
                                        track_ids.append(str(track.track_id))
                                        
                                        # Calculate velocity vector end points
                                        vel_scale = 0.5  # Scale factor for velocity vectors
                                        vx = track.state[0] + track.state[3] * vel_scale  # x + vx*scale
                                        vy = track.state[1] + track.state[4] * vel_scale  # y + vy*scale
                                        track_vx.append(vx)
                                        track_vy.append(vy)
                                    
                                    self.track_source.data = {
                                        'x': track_x,
                                        'y': track_y,
                                        'track_id': track_ids,
                                        'vx': track_vx,
                                        'vy': track_vy
                                    }
                                else:
                                    self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
                        else:
                            self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
                            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
                    
                    # Save data if recording is enabled
                    if self.is_recording and self.recording_file:
                        frame_number = point_cloud.metadata.get('frame_number', 0)
                        for i in range(min_length):
                            # Save both Cartesian and spherical coordinates
                            self.recording_file.write(
                                f"{frame_number},{x[i]:.3f},{y[i]:.3f},{z[i]:.3f},"
                                f"{point_cloud.velocity[i]:.3f},{point_cloud.range[i]:.3f},"
                                f"{point_cloud.azimuth[i]:.3f},{point_cloud.elevation[i]:.3f},"
                                f"{snr_values[i]:.3f}\n"
                            )
                        self.recording_file.flush()  # Ensure data is written to disk
                else:
                    # Clear all plots when no points are detected
                    self.data_source.data = {'x': [], 'y': [], 'velocity': [], 'size': []}
                    self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
                    self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}

            # Schedule next update if still running
            if self.is_running:
                pn.state.add_periodic_callback(self.update_plot, period=10, count=1)

        except StopIteration:
            # This happens when the radar stops sending data
            logger.warning("No more radar data available")
            self._stop_callback(None)
        except Exception as e:
            logger.error(f"Error updating plot: {e}")
            self.data_source.data = {'x': [], 'y': [], 'velocity': [], 'size': []}
            self.cluster_source.data = {'x': [], 'y': [], 'size': [], 'cluster_id': []}
            self.track_source.data = {'x': [], 'y': [], 'track_id': [], 'vx': [], 'vy': []}
            self._stop_callback(None)
    
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
            self.start_button,
            self.stop_button,
            self.record_button,
            pn.layout.Divider(),
            self.exit_button,     # Moved exit button up
            pn.layout.Divider(),
            self.modify_params_checkbox,  # Moved modify parameters checkbox down
            width=300,  # Reverted to 300 pixels for better usability
            styles={'background': '#f8f8f8', 'padding': '10px'}
        )
        
        # Create main content area
        main = pn.Column(
            pn.pane.Markdown('## Real-time Data'),
            self.plot,
            self.config_modal,  # Add the modal to main layout
            self.params_panel,  # Add the parameters panel to main layout
            styles={'padding': '10px'},
            max_width=1000  # Add max width to prevent excessive stretching on wide screens
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
        """Clean up resources when closing the GUI."""
        if self.is_running:
            self._stop_callback(None)
        if self.is_recording and self.recording_file:
            self.recording_file.close()
        if self.radar is not None and self.radar.is_connected():
            self.radar.close()

    def _detect_radar_type(self):
        """Auto-detect which radar is connected."""
        # Check serial ports and identify device type
        radar_base = RadarConnection()
        self.radar_type, self.config_file = radar_base.detect_radar_type()
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
            # Disable threshold slider if clustering is disabled
            self.mob_threshold_slider.disabled = not event.new
    
    def _tracking_callback(self, event):
        """Handle tracking checkbox changes."""
        if self.radar and self.radar.is_connected():
            self.enable_tracking = event.new
            logger.info(f"Tracking {'enabled' if event.new else 'disabled'}")
            # Disable threshold slider if tracking is disabled
            self.mob_threshold_slider.disabled = not event.new
