"""
Profile configuration view for radar settings.

This module provides a Panel-based view for configuring radar profile settings
with both basic and expert mode options.
"""

import logging
import param
import panel as pn
from panel.widgets import (
    Select, FloatSlider, FloatInput, IntSlider, IntInput, 
    Checkbox, StaticText, Button, TextAreaInput
)
from ..radar_config_models import RadarConfig, AntennaConfigEnum, GuiMonitorConfig

# Initialize logger
logger = logging.getLogger(__name__)

pn.extension()

class ProfileConfigView(param.Parameterized):
    """
    A Panel-based view for configuring the RadarConfig (radar profile section of the unified config).
    Now supports 'Expert Mode' for advanced/diagnostic parameters with proper form-based editors.
    """

    config = param.ClassSelector(class_=RadarConfig, is_instance=True)

    # Widgets for direct binding if not using pn.Param from Pydantic model directly
    # This approach gives more control over individual widget types and layout

    # --- Top Configuration Widgets ---
    antenna_config_select = param.Selector()

    # --- Scene Selection Widgets ---
    frame_rate_slider = param.ClassSelector(class_=FloatSlider)
    frame_rate_input = param.ClassSelector(class_=FloatInput)

    range_res_slider = param.ClassSelector(class_=FloatSlider)
    range_res_input = param.ClassSelector(class_=FloatInput)

    max_range_slider = param.ClassSelector(class_=FloatSlider)
    max_range_input = param.ClassSelector(class_=FloatInput)

    max_vel_slider = param.ClassSelector(class_=FloatSlider)
    max_vel_input = param.ClassSelector(class_=FloatInput)

    radial_vel_res_label = param.ClassSelector(class_=StaticText)
    radial_vel_res_select = param.ClassSelector(class_=Select)
    radial_vel_res_numeric_display = param.ClassSelector(class_=FloatInput)

    # --- Plot Selection Widgets ---
    plot_scatter_cb = param.ClassSelector(class_=Checkbox)
    plot_range_profile_cb = param.ClassSelector(class_=Checkbox)
    plot_noise_profile_cb = param.ClassSelector(class_=Checkbox)
    plot_range_azimuth_cb = param.ClassSelector(class_=Checkbox)
    plot_range_doppler_cb = param.ClassSelector(class_=Checkbox)
    plot_statistics_cb = param.ClassSelector(class_=Checkbox)

    # --- Expert Mode ---
    expert_mode = param.Boolean(default=False, doc="Enable expert/advanced parameter editing.")

    # Advanced/diagnostic widgets (replaced JSON editors with proper form widgets)
    # CFAR Configuration
    cfar_subframe_idx = param.ClassSelector(class_=IntInput)
    cfar_proc_direction = param.ClassSelector(class_=Select)
    cfar_average_mode = param.ClassSelector(class_=IntInput)
    cfar_win_len = param.ClassSelector(class_=IntSlider)
    cfar_guard_len = param.ClassSelector(class_=IntSlider)
    cfar_noise_div = param.ClassSelector(class_=IntInput)
    cfar_cyclic_mode = param.ClassSelector(class_=IntInput)
    cfar_threshold_scale = param.ClassSelector(class_=FloatSlider)
    cfar_peak_grouping_en = param.ClassSelector(class_=Checkbox)
    
    # Calibration DC Range Signal
    calib_dc_enabled = param.ClassSelector(class_=Checkbox)
    calib_dc_negative_bin = param.ClassSelector(class_=IntInput)
    calib_dc_positive_bin = param.ClassSelector(class_=IntInput)
    calib_dc_num_avg_frames = param.ClassSelector(class_=IntSlider)
    
    # AOA FOV Configuration
    aoa_min_azimuth = param.ClassSelector(class_=FloatSlider)
    aoa_max_azimuth = param.ClassSelector(class_=FloatSlider)
    aoa_min_elevation = param.ClassSelector(class_=FloatSlider)
    aoa_max_elevation = param.ClassSelector(class_=FloatSlider)
    
    # Multi-Object Beamforming
    mob_enabled = param.ClassSelector(class_=Checkbox)
    mob_threshold = param.ClassSelector(class_=FloatSlider)
    
    # GUI Monitor
    gui_detected_objects = param.ClassSelector(class_=Select)
    gui_range_profile_mode = param.ClassSelector(class_=Select)
    gui_noise_profile = param.ClassSelector(class_=Checkbox)
    gui_range_azimuth_heat_map = param.ClassSelector(class_=Checkbox)
    gui_range_doppler_heat_map = param.ClassSelector(class_=Checkbox)
    gui_stats_info = param.ClassSelector(class_=Checkbox)
    
    # Analog Monitor
    analog_rx_saturation = param.ClassSelector(class_=Checkbox)
    analog_sig_img_band = param.ClassSelector(class_=Checkbox)
    
    # Trigger Mode Configuration
    trigger_mode_select = param.ClassSelector(class_=Select)

    def __init__(self, config_instance: RadarConfig, **params):
        super().__init__(**params)
        self.config = config_instance
        self._init_widgets()
        self._init_expert_widgets()
        self._link_widgets_to_config()
        self._update_gui_monitor_config(None)

    def _init_widgets(self):
        # Initialize top selectors
        self.param.antenna_config_select.objects = list(AntennaConfigEnum)
        self.antenna_config_select = self.config.antenna_config

        # Scene Selection
        # Helper function to extract ge/le from metadata
        def get_slider_bounds(field_info, default_ge, default_le):
            start_val = None
            end_val = None
            if field_info and hasattr(field_info, 'metadata'):
                for meta_item in field_info.metadata:
                    if hasattr(meta_item, 'ge'):
                        start_val = meta_item.ge
                    if hasattr(meta_item, 'le'):
                        end_val = meta_item.le
            return start_val if start_val is not None else default_ge, \
                   end_val if end_val is not None else default_le

        # Frame Rate
        frame_rate_field = self.config.model_fields['frame_rate_fps']
        fr_start, fr_end = get_slider_bounds(frame_rate_field, 1.0, 30.0)
        self.frame_rate_slider = FloatSlider(
            name="Frame Rate (fps)", 
            start=fr_start, 
            end=fr_end,
            value=self.config.frame_rate_fps, step=1, bar_color='#FF0000' # Red color from image
        )
        self.frame_rate_input = FloatInput(
            name="", value=self.config.frame_rate_fps, width=80
        )

        # Range Resolution
        range_res_field = self.config.model_fields['range_resolution_m']
        rr_start, rr_end = get_slider_bounds(range_res_field, 0.039, 0.047)
        self.range_res_slider = FloatSlider(
            name="Range Resolution (m)", 
            start=rr_start,
            end=rr_end,
            value=self.config.range_resolution_m, step=0.001, format='0.000', bar_color='#FF0000'
        )
        self.range_res_input = FloatInput(
            name="", value=self.config.range_resolution_m, width=80, format='0.000'
        )

        # Max Unambiguous Range
        max_range_field = self.config.model_fields['max_unambiguous_range_m']
        mr_start, mr_end = get_slider_bounds(max_range_field, 3.95, 18.02)
        self.max_range_slider = FloatSlider(
            name="Maximum Unambiguous Range (m)",
            start=mr_start,
            end=mr_end,
            value=self.config.max_unambiguous_range_m, step=0.01, format='0.00', bar_color='#FF0000'
        )
        self.max_range_input = FloatInput(
            name="", value=self.config.max_unambiguous_range_m, width=80, format='0.00'
        )
        
        # Max Radial Velocity
        max_vel_field = self.config.model_fields['max_radial_velocity_ms']
        mv_start, mv_end = get_slider_bounds(max_vel_field, 0.27, 6.39)
        self.max_vel_slider = FloatSlider(
            name="Maximum Radial Velocity (m/s)",
            start=mv_start,
            end=mv_end,
            value=self.config.max_radial_velocity_ms, step=0.01, format='0.00', bar_color='#FF0000'
        )
        self.max_vel_input = FloatInput(
            name="", value=self.config.max_radial_velocity_ms, width=80, format='0.00'
        )
        
        # Radial Velocity Resolution
        self.radial_vel_res_label = StaticText(value="Radial Velocity Resolution (m/s)")
        # Ensure the initial value for Select is one of its options, otherwise Panel might error or pick first
        initial_rvr = self.config.radial_velocity_resolution_ms
        rvr_options = [0.07, 0.13]
        if initial_rvr not in rvr_options:
            initial_rvr = rvr_options[0] # Default to first option if current config value isn't valid for select
            self.config.radial_velocity_resolution_ms = initial_rvr # Update config to match default UI
            
        self.radial_vel_res_select = Select(
            name="", 
            options=rvr_options, 
            value=initial_rvr,
            width=80 # Adjusted width to be similar to FloatInput
        )
        self.radial_vel_res_numeric_display = FloatInput(
            name="", 
            value=initial_rvr, 
            width=80, format='0.00', disabled=True
        )

        # Plot Selection
        self.plot_scatter_cb = Checkbox(name="Scatter Plot", value=self.config.plot_scatter)
        self.plot_range_profile_cb = Checkbox(name="Range Profile", value=self.config.plot_range_profile)
        self.plot_noise_profile_cb = Checkbox(name="Noise Profile", value=self.config.plot_noise_profile)
        self.plot_range_azimuth_cb = Checkbox(name="Range Azimuth Heat Map", value=self.config.plot_range_azimuth_heat_map)
        self.plot_range_doppler_cb = Checkbox(name="Range Doppler Heat Map", value=self.config.plot_range_doppler_heat_map)
        self.plot_statistics_cb = Checkbox(name="Statistics", value=self.config.plot_statistics)

    def _init_expert_widgets(self):
        """Initialize expert mode widgets with proper form controls instead of JSON editors."""
        
        # CFAR Configuration
        self.cfar_subframe_idx = IntInput(name="Subframe Index", value=-1, width=100)
        self.cfar_proc_direction = Select(name="Processing Direction", options=["Range (0)", "Doppler (1)"], value="Range (0)", width=150)
        self.cfar_average_mode = IntInput(name="Average Mode", value=2, width=100)
        self.cfar_win_len = IntSlider(name="Window Length", start=4, end=32, value=8, step=2, width=200)
        self.cfar_guard_len = IntSlider(name="Guard Length", start=2, end=16, value=4, step=1, width=200)
        self.cfar_noise_div = IntInput(name="Noise Divider", value=3, width=100)
        self.cfar_cyclic_mode = IntInput(name="Cyclic Mode", value=0, width=100)
        self.cfar_threshold_scale = FloatSlider(name="Threshold Scale", start=1.0, end=50.0, value=15.0, step=0.5, width=200)
        self.cfar_peak_grouping_en = Checkbox(name="Peak Grouping", value=False)
        
        # Calibration DC Range Signal
        self.calib_dc_enabled = Checkbox(name="Enable DC Calibration", value=False)
        self.calib_dc_negative_bin = IntInput(name="Negative Bin Index", value=-5, width=100)
        self.calib_dc_positive_bin = IntInput(name="Positive Bin Index", value=8, width=100)
        self.calib_dc_num_avg_frames = IntSlider(name="Number of Avg Frames", start=1, end=512, value=256, step=1, width=200)
        
        # AOA FOV Configuration
        self.aoa_min_azimuth = FloatSlider(name="Min Azimuth (deg)", start=-90.0, end=0.0, value=-90.0, step=1.0, width=200)
        self.aoa_max_azimuth = FloatSlider(name="Max Azimuth (deg)", start=0.0, end=90.0, value=90.0, step=1.0, width=200)
        self.aoa_min_elevation = FloatSlider(name="Min Elevation (deg)", start=-90.0, end=0.0, value=-90.0, step=1.0, width=200)
        self.aoa_max_elevation = FloatSlider(name="Max Elevation (deg)", start=0.0, end=90.0, value=90.0, step=1.0, width=200)
        
        # Multi-Object Beamforming
        self.mob_enabled = Checkbox(name="Enable Multi-Object Beamforming", value=True)
        self.mob_threshold = FloatSlider(name="MOB Threshold", start=0.0, end=1.0, value=0.5, step=0.01, width=200)
        
        # GUI Monitor
        self.gui_detected_objects = Select(name="Detected Objects", options=["None (0)", "Objects + Side Info (1)", "Objects Only (2)"], value="Objects + Side Info (1)", width=200)
        # Set initial value based on current config
        initial_mode = "Log Magnitude" if getattr(self.config, 'range_profile_mode', 'log_magnitude') == 'log_magnitude' else "Complex"
        self.gui_range_profile_mode = Select(name="Range Profile Mode", options=["Log Magnitude", "Complex"], value=initial_mode, width=200)
        #self.gui_noise_profile = Checkbox(name="Noise Profile", value=self.config.plot_noise_profile)
        #self.gui_range_azimuth_heat_map = Checkbox(name="Range Azimuth Heat Map", value=self.config.plot_range_azimuth_heat_map)
        #self.gui_range_doppler_heat_map = Checkbox(name="Range Doppler Heat Map", value=self.config.plot_range_doppler_heat_map)
        #self.gui_stats_info = Checkbox(name="Statistics Info", value=self.config.plot_statistics)
        
        # Analog Monitor
        self.analog_rx_saturation = Checkbox(name="RX Saturation Monitoring", value=False)
        self.analog_sig_img_band = Checkbox(name="Signal Image Band Monitoring", value=False)
        
        # Trigger Mode Configuration
        trigger_mode_options = [
            "Timer-based (0)",
            "Software (1)", 
            "Hardware (2)"
        ]
        # Get current trigger mode from config, default to 0 (timer-based)
        current_trigger_mode = getattr(self.config, 'trigger_mode', 0)
        self.trigger_mode_select = Select(
            name="Trigger Mode",
            options=trigger_mode_options,
            value=trigger_mode_options[current_trigger_mode],
            width=200
        )

    def _link_widgets_to_config(self):
        # Link top selectors
        self.param.watch(self._on_antenna_config_change, 'antenna_config_select')

        # Link Scene Selection sliders and inputs bidirectionally
        self.frame_rate_slider.param.watch(lambda event: setattr(self.frame_rate_input, 'value', event.new), 'value')
        self.frame_rate_input.param.watch(lambda event: setattr(self.frame_rate_slider, 'value', event.new), 'value')
        self.frame_rate_slider.param.watch(lambda event: setattr(self.config, 'frame_rate_fps', event.new), 'value')
        self.frame_rate_input.param.watch(lambda event: setattr(self.config, 'frame_rate_fps', event.new), 'value')
        
        # Add logging for frame rate changes
        self.frame_rate_slider.param.watch(self._on_frame_rate_change, 'value')
        self.frame_rate_input.param.watch(self._on_frame_rate_change, 'value')

        self.range_res_slider.param.watch(lambda event: setattr(self.range_res_input, 'value', event.new), 'value')
        self.range_res_input.param.watch(lambda event: setattr(self.range_res_slider, 'value', event.new), 'value')
        self.range_res_slider.param.watch(lambda event: setattr(self.config, 'range_resolution_m', event.new), 'value')

        self.max_range_slider.param.watch(lambda event: setattr(self.max_range_input, 'value', event.new), 'value')
        self.max_range_input.param.watch(lambda event: setattr(self.max_range_slider, 'value', event.new), 'value')
        self.max_range_slider.param.watch(lambda event: setattr(self.config, 'max_unambiguous_range_m', event.new), 'value')

        self.max_vel_slider.param.watch(lambda event: setattr(self.max_vel_input, 'value', event.new), 'value')
        self.max_vel_input.param.watch(lambda event: setattr(self.max_vel_slider, 'value', event.new), 'value')
        self.max_vel_slider.param.watch(lambda event: setattr(self.config, 'max_radial_velocity_ms', event.new), 'value')
        
        # Radial velocity resolution is now user-settable via Select
        self.radial_vel_res_select.param.watch(self._on_radial_vel_res_select_change, 'value')

        # Link Plot Selection checkboxes
        self.plot_scatter_cb.param.watch(lambda event: setattr(self.config, 'plot_scatter', event.new), 'value')
        self.plot_range_profile_cb.param.watch(lambda event: setattr(self.config, 'plot_range_profile', event.new), 'value')
        self.plot_noise_profile_cb.param.watch(lambda event: setattr(self.config, 'plot_noise_profile', event.new), 'value')
        self.plot_range_azimuth_cb.param.watch(lambda event: setattr(self.config, 'plot_range_azimuth_heat_map', event.new), 'value')
        self.plot_range_doppler_cb.param.watch(lambda event: setattr(self.config, 'plot_range_doppler_heat_map', event.new), 'value')
        self.plot_statistics_cb.param.watch(lambda event: setattr(self.config, 'plot_statistics', event.new), 'value')

        # Link plot selections to GUI monitor widgets directly
        self.plot_range_profile_cb.param.watch(lambda event: setattr(self.gui_range_profile_mode, 'value', event.new), 'value')
        #self.plot_noise_profile_cb.param.watch(lambda event: setattr(self.gui_noise_profile, 'value', event.new), 'value')
        #self.plot_range_azimuth_cb.param.watch(lambda event: setattr(self.gui_range_azimuth_heat_map, 'value', event.new), 'value')
        #self.plot_range_doppler_cb.param.watch(lambda event: setattr(self.gui_range_doppler_heat_map, 'value', event.new), 'value')
        #self.plot_statistics_cb.param.watch(lambda event: setattr(self.gui_stats_info, 'value', event.new), 'value')

        # Link expert mode widgets to config
        self._link_expert_widgets()

    def _link_expert_widgets(self):
        """Link expert mode widgets to the configuration."""
        # CFAR Configuration
        self.cfar_subframe_idx.param.watch(self._update_cfar_config, 'value')
        self.cfar_proc_direction.param.watch(self._update_cfar_config, 'value')
        self.cfar_average_mode.param.watch(self._update_cfar_config, 'value')
        self.cfar_win_len.param.watch(self._update_cfar_config, 'value')
        self.cfar_guard_len.param.watch(self._update_cfar_config, 'value')
        self.cfar_noise_div.param.watch(self._update_cfar_config, 'value')
        self.cfar_cyclic_mode.param.watch(self._update_cfar_config, 'value')
        self.cfar_threshold_scale.param.watch(self._update_cfar_config, 'value')
        self.cfar_peak_grouping_en.param.watch(self._update_cfar_config, 'value')
        
        # Calibration DC Range Signal
        self.calib_dc_enabled.param.watch(self._update_calib_dc_config, 'value')
        self.calib_dc_negative_bin.param.watch(self._update_calib_dc_config, 'value')
        self.calib_dc_positive_bin.param.watch(self._update_calib_dc_config, 'value')
        self.calib_dc_num_avg_frames.param.watch(self._update_calib_dc_config, 'value')
        
        # AOA FOV Configuration
        self.aoa_min_azimuth.param.watch(self._update_aoa_config, 'value')
        self.aoa_max_azimuth.param.watch(self._update_aoa_config, 'value')
        self.aoa_min_elevation.param.watch(self._update_aoa_config, 'value')
        self.aoa_max_elevation.param.watch(self._update_aoa_config, 'value')
        
        # Multi-Object Beamforming
        self.mob_enabled.param.watch(self._update_mob_config, 'value')
        self.mob_threshold.param.watch(self._update_mob_config, 'value')
        
        # GUI Monitor
        self.gui_detected_objects.param.watch(self._update_gui_monitor_config, 'value')
        self.gui_range_profile_mode.param.watch(self._update_gui_monitor_config, 'value')
        #self.gui_noise_profile.param.watch(self._update_gui_monitor_config, 'value')
        #self.gui_range_azimuth_heat_map.param.watch(self._update_gui_monitor_config, 'value')
        #self.gui_range_doppler_heat_map.param.watch(self._update_gui_monitor_config, 'value')
        #self.gui_stats_info.param.watch(self._update_gui_monitor_config, 'value')
        
        # Analog Monitor
        self.analog_rx_saturation.param.watch(self._update_analog_monitor_config, 'value')
        self.analog_sig_img_band.param.watch(self._update_analog_monitor_config, 'value')
        
        # Trigger Mode
        self.trigger_mode_select.param.watch(self._update_trigger_mode_config, 'value')

    def _update_cfar_config(self, event):
        """Update CFAR configuration from widget values."""
        if not hasattr(self.config, 'cfar_cfg') or self.config.cfar_cfg is None:
            from ..radar_config_models import CfarConfig
            self.config.cfar_cfg = CfarConfig(
                subframe_idx=self.cfar_subframe_idx.value,
                proc_direction=0 if "Range" in self.cfar_proc_direction.value else 1,
                average_mode=self.cfar_average_mode.value,
                win_len=self.cfar_win_len.value,
                guard_len=self.cfar_guard_len.value,
                noise_div=self.cfar_noise_div.value,
                cyclic_mode=self.cfar_cyclic_mode.value,
                threshold_scale=self.cfar_threshold_scale.value,
                peak_grouping_en=self.cfar_peak_grouping_en.value
            )
        else:
            self.config.cfar_cfg.subframe_idx = self.cfar_subframe_idx.value
            self.config.cfar_cfg.proc_direction = 0 if "Range" in self.cfar_proc_direction.value else 1
            self.config.cfar_cfg.average_mode = self.cfar_average_mode.value
            self.config.cfar_cfg.win_len = self.cfar_win_len.value
            self.config.cfar_cfg.guard_len = self.cfar_guard_len.value
            self.config.cfar_cfg.noise_div = self.cfar_noise_div.value
            self.config.cfar_cfg.cyclic_mode = self.cfar_cyclic_mode.value
            self.config.cfar_cfg.threshold_scale = self.cfar_threshold_scale.value
            self.config.cfar_cfg.peak_grouping_en = self.cfar_peak_grouping_en.value

    def _update_calib_dc_config(self, event):
        """Update Calibration DC Range Signal configuration from widget values."""
        if not hasattr(self.config, 'calib_dc_range_sig') or self.config.calib_dc_range_sig is None:
            from ..radar_config_models import CalibDcRangeSigConfig
            self.config.calib_dc_range_sig = CalibDcRangeSigConfig(
                subframe_idx=-1,
                enabled=self.calib_dc_enabled.value,
                negative_bin_idx=self.calib_dc_negative_bin.value,
                positive_bin_idx=self.calib_dc_positive_bin.value,
                num_avg_frames=self.calib_dc_num_avg_frames.value
            )
        else:
            self.config.calib_dc_range_sig.enabled = self.calib_dc_enabled.value
            self.config.calib_dc_range_sig.negative_bin_idx = self.calib_dc_negative_bin.value
            self.config.calib_dc_range_sig.positive_bin_idx = self.calib_dc_positive_bin.value
            self.config.calib_dc_range_sig.num_avg_frames = self.calib_dc_num_avg_frames.value

    def _update_aoa_config(self, event):
        """Update AOA FOV configuration from widget values."""
        if not hasattr(self.config, 'aoa_fov_cfg') or self.config.aoa_fov_cfg is None:
            from ..radar_config_models import AoaFovConfig
            self.config.aoa_fov_cfg = AoaFovConfig(
                subframe_idx=-1,
                min_azimuth_deg=self.aoa_min_azimuth.value,
                max_azimuth_deg=self.aoa_max_azimuth.value,
                min_elevation_deg=self.aoa_min_elevation.value,
                max_elevation_deg=self.aoa_max_elevation.value
            )
        else:
            self.config.aoa_fov_cfg.min_azimuth_deg = self.aoa_min_azimuth.value
            self.config.aoa_fov_cfg.max_azimuth_deg = self.aoa_max_azimuth.value
            self.config.aoa_fov_cfg.min_elevation_deg = self.aoa_min_elevation.value
            self.config.aoa_fov_cfg.max_elevation_deg = self.aoa_max_elevation.value

    def _update_mob_config(self, event):
        """Update Multi-Object Beamforming configuration from widget values."""
        if not hasattr(self.config, 'multi_obj_beam_forming') or self.config.multi_obj_beam_forming is None:
            from ..radar_config_models import MultiObjBeamFormingConfig
            self.config.multi_obj_beam_forming = MultiObjBeamFormingConfig(
                subframe_idx=-1,
                enabled=self.mob_enabled.value,
                threshold=self.mob_threshold.value
            )
        else:
            self.config.multi_obj_beam_forming.enabled = self.mob_enabled.value
            self.config.multi_obj_beam_forming.threshold = self.mob_threshold.value

    def _update_gui_monitor_config(self, event):
        """Update GUI monitor configuration based on widget values."""
        try:
            # Parse detected objects value
            detected_objects = int(self.gui_detected_objects.value.split('(')[1].split(')')[0])
            
            # Update config with new GUI monitor settings
            self.config.gui_monitor = GuiMonitorConfig(
                detected_objects=detected_objects,
                range_profile_enabled=self.config.plot_range_profile,  # Use the main config setting
                range_profile_mode="log_magnitude" if self.gui_range_profile_mode.value == "Log Magnitude" else "complex",
                noise_profile=getattr(self, 'gui_noise_profile', None) and self.gui_noise_profile.value or False,
                range_azimuth_heat_map=getattr(self, 'gui_range_azimuth_heat_map', None) and self.gui_range_azimuth_heat_map.value or False,
                range_doppler_heat_map=getattr(self, 'gui_range_doppler_heat_map', None) and self.gui_range_doppler_heat_map.value or False,
                stats_info=getattr(self, 'gui_stats_info', None) and self.gui_stats_info.value or True
            )
            
            # Also update the main config plot settings to match (only if widgets exist)
            self.config.range_profile_mode = "log_magnitude" if self.gui_range_profile_mode.value == "Log Magnitude" else "complex"
            if hasattr(self, 'gui_noise_profile') and self.gui_noise_profile is not None:
                self.config.plot_noise_profile = self.gui_noise_profile.value
            if hasattr(self, 'gui_range_azimuth_heat_map') and self.gui_range_azimuth_heat_map is not None:
                self.config.plot_range_azimuth_heat_map = self.gui_range_azimuth_heat_map.value
            if hasattr(self, 'gui_range_doppler_heat_map') and self.gui_range_doppler_heat_map is not None:
                self.config.plot_range_doppler_heat_map = self.gui_range_doppler_heat_map.value
            if hasattr(self, 'gui_stats_info') and self.gui_stats_info is not None:
                self.config.plot_statistics = self.gui_stats_info.value
            
        except Exception as e:
            logger.error(f"Error updating GUI monitor config: {e}")

    def _update_analog_monitor_config(self, event):
        """Update Analog Monitor configuration from widget values."""
        if not hasattr(self.config, 'analog_monitor') or self.config.analog_monitor is None:
            from ..radar_config_models import AnalogMonitorConfig
            self.config.analog_monitor = AnalogMonitorConfig(
                rx_saturation=self.analog_rx_saturation.value,
                sig_img_band=self.analog_sig_img_band.value
            )
        else:
            self.config.analog_monitor.rx_saturation = self.analog_rx_saturation.value
            self.config.analog_monitor.sig_img_band = self.analog_sig_img_band.value

    def _update_trigger_mode_config(self, event):
        """Update trigger mode configuration from widget values."""
        # Extract the mode number from the selected option
        # Options are: "Timer-based (0)", "Software (1)", "Hardware (2)"
        selected_option = event.new
        if "(0)" in selected_option:
            mode = 0
        elif "(1)" in selected_option:
            mode = 1
        elif "(2)" in selected_option:
            mode = 2
        else:
            mode = 0  # Default to timer-based
            
        # Update the config
        self.config.trigger_mode = mode
        logger.info(f"Trigger mode updated to: {mode} ({selected_option})")

    # Callbacks for selector changes
    def _on_antenna_config_change(self, event):
        # event.new is now an AntennaConfigEnum instance
        if isinstance(event.new, AntennaConfigEnum):
            self.config.antenna_config = event.new
        else:
            try:
                self.config.antenna_config = AntennaConfigEnum(event.new)
            except ValueError:
                self.config.antenna_config = AntennaConfigEnum.CFG_4RX_3TX_15DEG_ELEV
    
    def _on_radial_vel_res_select_change(self, event):
        """Handles changes from the radial velocity resolution Select widget."""
        new_val = event.new
        self.config.radial_velocity_resolution_ms = new_val
        self.radial_vel_res_numeric_display.value = new_val
    
    def _on_frame_rate_change(self, event):
        """Handles changes from the frame rate slider/input widgets."""
        import logging
        logger = logging.getLogger(__name__)
        new_fps = event.new
        frame_period_ms = 1000.0 / new_fps
        logger.info(f"ProfileConfigView frame rate changed: {new_fps:.1f} fps = {frame_period_ms:.1f} ms")
        self.config.frame_rate_fps = new_fps

    def _create_widget_cache(self):
        """Create and cache widgets to prevent recreation."""
        if hasattr(self, '_widget_cache'):
            return self._widget_cache
            
        # Create layouts
        top_config = self._create_top_config_layout()
        scene_selection = self._create_scene_selection_layout()
        plot_selection = self._create_plot_selection_layout()
        advanced_section = self._create_advanced_section_layout()
        
        self._widget_cache = {
            'top_config': top_config,
            'scene_selection': scene_selection,
            'plot_selection': plot_selection,
            'advanced_section': advanced_section
        }
        return self._widget_cache
    
    def _create_top_config_layout(self):
        """Create top configuration layout."""
        return pn.Row(
            pn.Column(
                StaticText(value="<b>Antenna Config (Azimuth Res - deg)</b>"), 
                pn.Param(self.param.antenna_config_select, widgets={ 'antenna_config_select': pn.widgets.Select})
            )
        )
    
    def _create_scene_selection_layout(self):
        """Create scene selection layout."""
        return pn.Column(
            StaticText(value="<h2>Scene Selection</h2>"),
            pn.Row(self.frame_rate_slider, self.frame_rate_input, sizing_mode='stretch_width'),
            pn.Row(self.range_res_slider, self.range_res_input, sizing_mode='stretch_width'),
            pn.Row(self.max_range_slider, self.max_range_input, sizing_mode='stretch_width'),
            pn.Row(self.max_vel_slider, self.max_vel_input, sizing_mode='stretch_width'),
            pn.Row(self.radial_vel_res_label, self.radial_vel_res_select, self.radial_vel_res_numeric_display, sizing_mode='stretch_width')
        )
    
    def _create_plot_selection_layout(self):
        """Create plot selection layout."""
        return pn.Column(
            StaticText(value="<h2>Plot Selection</h2>"),
            pn.Row(
                pn.Column(self.plot_scatter_cb, self.plot_range_profile_cb, self.plot_noise_profile_cb),
                pn.Column(self.plot_range_azimuth_cb, self.plot_range_doppler_cb, self.plot_statistics_cb)
            )
        )
    
    def _create_advanced_section_layout(self):
        """Create advanced section layout."""
        return pn.Column(
            pn.pane.Markdown("## Advanced/Diagnostic Parameters (Expert Mode)"),
            
            # CFAR Configuration
            pn.pane.Markdown("### CFAR Detection Configuration"),
            pn.Row(
                pn.Column(self.cfar_subframe_idx, self.cfar_proc_direction, self.cfar_average_mode),
                pn.Column(self.cfar_win_len, self.cfar_guard_len, self.cfar_noise_div),
                pn.Column(self.cfar_cyclic_mode, self.cfar_threshold_scale, self.cfar_peak_grouping_en)
            ),
            
            pn.layout.Divider(),
            
            # Calibration DC Range Signal
            pn.pane.Markdown("### Calibration DC Range Signal"),
            pn.Row(
                pn.Column(self.calib_dc_enabled, self.calib_dc_negative_bin, self.calib_dc_positive_bin),
                pn.Column(self.calib_dc_num_avg_frames)
            ),
            
            pn.layout.Divider(),
            
            # AOA FOV Configuration
            pn.pane.Markdown("### Angle of Arrival FOV Configuration"),
            pn.Row(
                pn.Column(self.aoa_min_azimuth, self.aoa_max_azimuth),
                pn.Column(self.aoa_min_elevation, self.aoa_max_elevation)
            ),
            
            pn.layout.Divider(),
            
            # Multi-Object Beamforming
            pn.pane.Markdown("### Multi-Object Beamforming"),
            pn.Row(self.mob_enabled, self.mob_threshold),
            
            pn.layout.Divider(),
            
            # GUI Monitor
            pn.pane.Markdown("### GUI Monitor Configuration"),
            pn.Row(
                pn.Column(self.gui_detected_objects, self.gui_range_profile_mode),
                pn.Column(self.gui_noise_profile, self.gui_range_azimuth_heat_map, self.gui_range_doppler_heat_map, self.gui_stats_info)
            ),
            
            pn.layout.Divider(),
            
            # Analog Monitor
            pn.pane.Markdown("### Analog Monitor Configuration"),
            pn.Row(self.analog_rx_saturation, self.analog_sig_img_band),
            
            pn.layout.Divider(),
            
            # Trigger Mode Configuration
            pn.pane.Markdown("### Trigger Mode Configuration"),
            pn.Row(self.trigger_mode_select)
        )

    @pn.depends('expert_mode')
    def view(self):
        # Use cached widgets
        cache = self._create_widget_cache()
        
        expert_toggle = pn.widgets.Checkbox(name="Expert Mode (show advanced parameters)", value=self.expert_mode, width=250)
        def _toggle_expert(event):
            self.expert_mode = event.new
        expert_toggle.param.watch(_toggle_expert, 'value')

        # Advanced section visibility depends on expert_mode
        advanced_section = cache['advanced_section']
        advanced_section.visible = self.expert_mode

        return pn.Column(
            expert_toggle,
            cache['top_config'],
            pn.layout.Divider(),
            cache['scene_selection'],
            pn.layout.Divider(),
            cache['plot_selection'],
            pn.layout.Divider(),
            advanced_section,
            sizing_mode='stretch_width'
        )

# Example of how to use this view
if __name__ == "__main__":
    # Create a default config instance
    default_config = RadarConfig()

    # Create the view with the config instance
    config_view_panel = ProfileConfigView(config_instance=default_config)

    # To display it in a Jupyter notebook or serve it:
    # config_view_panel.view.show() # For serving in a new browser tab
    # config_view_panel.view.servable() # For embedding in a Panel server

    # For simple display in a script that exits, you might need to serve and open manually.
    # For now, let's just verify it builds the panel
    test_panel = config_view_panel.view
    print(f"Panel object created: {type(test_panel)}")
    print("To see the GUI, uncomment .show() or .servable() and run as a script, or use in Jupyter.")

    # Example of changing a value in the config and (ideally) seeing it reflect if widgets were bound to config directly
    # (This requires more work if not using pn.Param with the pydantic object itself as the parameterized object)
    # default_config.frame_rate_fps = 15
    # print(f"Changed config fps to: {default_config.frame_rate_fps}")
    # print(f"Slider fps: {config_view_panel.frame_rate_slider.value}") # This won't auto-update with current setup
 