"""Simple Bokeh GUI for the xwr68xxisk radar sensor evaluation kit."""

import numpy as np
import panel as pn
import holoviews as hv
from bokeh.plotting import figure
from bokeh.models import ColorBar, LinearColorMapper, ColumnDataSource
import colorcet as cc
from xwr68xxisk.radar import XWR68xxRadar, RadarConnectionError, AWR2544Radar
from xwr68xxisk.parse import RadarData
import time
import os
import logging
from datetime import datetime
from panel.widgets import TextAreaInput, StaticText, Button, FileInput, Select
from xwr68xxisk.radar import RadarConnection, create_radar
import socket
from xwr68xxisk import defaultconfig

logger = logging.getLogger(__name__)

TIMER_PERIOD = 90

# Initialize extensions (fix order and syntax)
hv.extension('bokeh')
pn.extension(design="material", sizing_mode="stretch_width")


class RadarGUI:
    def __init__(self):
        # Initialize radar connection
        # Note: Actual connection to the physical device happens later via connect() method
        self.radar = None
        self.radar_type = None  # Will be set during connection
        
        # Load default configuration - will be set when radar type is detected
        self.config_file = None
        
        # Add timing variable
        self.last_update_time = None
        
        # Initialize plot data
        self.scatter_source = None
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
        self.clutter_removal_checkbox = pn.widgets.Checkbox(name='Enable Clutter Removal', value=False)
        
        # Set up callbacks
        self.load_config_button.param.watch(self._load_config_callback, 'value')
        self.connect_button.on_click(self._connect_callback)
        self.start_button.on_click(self._start_callback)
        self.stop_button.on_click(self._stop_callback)
        self.record_button.on_click(self._record_callback)
        self.exit_button.on_click(self._exit_callback)
        self.clutter_removal_checkbox.param.watch(self._clutter_removal_callback, 'value')
        self.start_button.disabled = True
        self.stop_button.disabled = True
        self.record_button.disabled = True
        self.clutter_removal_checkbox.disabled = True  # Initially disabled until connected
        
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
            
            # Update version info in the modal
            if self.radar.version_info:
                formatted_info = '\n'.join(str(line) for line in self.radar.version_info)
                self.version_info.value = formatted_info
                
            # Set the configuration text directly
            if self.config_file:
                self.config_text.value = self.config_file
            
            self.connect_button.loading = False
            self.connect_button.name = "Connected"
            self.connect_button.button_type = "success"
            self.start_button.disabled = False
            self.config_button.disabled = False
            self.clutter_removal_checkbox.disabled = False  # Enable clutter removal checkbox
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
            # Write header
            self.recording_file.write("frame,x,y,velocity,snr\n")
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
            width=1200,    # Doubled from 600
            height=800,    # Doubled from 400
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
        """Update the plot with new radar data."""
        
        try:
            # Get actual radar data
            data = RadarData(self.radar)
            if data is not None and data.pc is not None:
                x, y, z, velocity = data.pc
                
                # Clip x and y values to plot range
                x = np.clip(x, -2.5, 2.5)
                y = np.clip(y, 0, 5)
                
                # Clip velocity to color mapper range
                velocity = np.clip(velocity, -1, 1)
                
                # Get original SNR values (0-60 range)
                # Ensure snr_values has same length as position data
                if data.snr and len(data.snr) == len(x):
                    snr_values = np.array(data.snr)
                else:
                    snr_values = np.ones(len(x)) * 30  # Default to mid-range if no SNR or length mismatch
                
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

                # Save data if recording is enabled
                if self.is_recording and self.recording_file:
                    frame_number = data.frame_number if data.frame_number is not None else 0
                    for i in range(min_length):
                        self.recording_file.write(f"{frame_number},{x[i]:.3f},{y[i]:.3f},{velocity[i]:.3f},{snr_values[i]:.3f}\n")
                    self.recording_file.flush()  # Ensure data is written to disk
            else:
                # Clear the plot when no data is available
                self.data_source.data = {
                    'x': [],
                    'y': [],
                    'velocity': [],
                    'size': []
                }

            # Schedule next update if still running
            if self.is_running:
                pn.state.add_periodic_callback(self.update_plot, period=10, count=1)

        except Exception as e:
            logger.error(f"Error updating plot: {e}")
            # Clear the plot on error
            self.data_source.data = {
                'x': [],
                'y': [],
                'velocity': [],
                'size': []
            }
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
            self.clutter_removal_checkbox,  # Add clutter removal checkbox
            pn.layout.Divider(),
            self.exit_button,
            width=300,
            styles={'background': '#f8f8f8', 'padding': '10px'}
        )
        
        # Create main content area
        main = pn.Column(
            pn.pane.Markdown('## Real-time Data'),
            self.plot,
            self.config_modal,  # Add the modal to main layout
            styles={'padding': '10px'}
        )
        
        # Add CSS for modal styling
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
        """])
        
        # Combine everything into a template
        template = pn.template.MaterialTemplate(
            title='XWR68XX ISK Radar GUI',
            sidebar=sidebar,
            main=main,
            header=header
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
