import panel as pn
import param
from panel.widgets import FloatSlider, FloatInput, Select, Checkbox, StaticText, JSONEditor

# Assuming radar_config_models.py is accessible in the PYTHONPATH
# Adjust import path if necessary, e.g., from ..radar_config_models import ...
from ..radar_config_models import RadarConfig, AntennaConfigEnum

pn.extension()

class ProfileConfigView(param.Parameterized):
    """
    A Panel-based view for configuring the RadarConfig (radar profile section of the unified config).
    Now supports 'Expert Mode' for advanced/diagnostic parameters.
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

    # Advanced/diagnostic widgets (initialized in _init_expert_widgets)
    cfar_cfgs_editor = param.ClassSelector(class_=JSONEditor, default=None)
    calib_dc_range_sig_editor = param.ClassSelector(class_=JSONEditor, default=None)
    comp_range_bias_and_rx_chan_phase_editor = param.ClassSelector(class_=JSONEditor, default=None)
    measure_range_bias_and_rx_chan_phase_editor = param.ClassSelector(class_=JSONEditor, default=None)
    aoa_fov_cfg_editor = param.ClassSelector(class_=JSONEditor, default=None)
    cfar_fov_cfgs_editor = param.ClassSelector(class_=JSONEditor, default=None)
    extended_max_velocity_editor = param.ClassSelector(class_=JSONEditor, default=None)
    cq_rx_sat_monitor_editor = param.ClassSelector(class_=JSONEditor, default=None)
    cq_sig_img_monitor_editor = param.ClassSelector(class_=JSONEditor, default=None)
    analog_monitor_editor = param.ClassSelector(class_=JSONEditor, default=None)
    lvds_stream_cfg_editor = param.ClassSelector(class_=JSONEditor, default=None)
    bpm_cfg_editor = param.ClassSelector(class_=JSONEditor, default=None)
    calib_data_editor = param.ClassSelector(class_=JSONEditor, default=None)

    def __init__(self, config_instance: RadarConfig, **params):
        super().__init__(**params)
        self.config = config_instance
        self._init_widgets()
        self._init_expert_widgets()
        self._link_widgets_to_config()

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
        # Use JSONEditor for flexible editing of dict/list fields
        self.cfar_cfgs_editor = JSONEditor(
            value=[c.model_dump() if hasattr(c, 'model_dump') else c for c in (self.config.cfar_cfgs or [])],
            name="CFAR Configs (Advanced)", height=120, width=500)
        self.calib_dc_range_sig_editor = JSONEditor(
            value=self.config.calib_dc_range_sig.model_dump() if getattr(self.config, 'calib_dc_range_sig', None) and hasattr(self.config.calib_dc_range_sig, 'model_dump') else (self.config.calib_dc_range_sig or {}),
            name="Calib DC Range Sig (Advanced)", height=80, width=500)
        self.comp_range_bias_and_rx_chan_phase_editor = JSONEditor(
            value=self.config.comp_range_bias_and_rx_chan_phase or [],
            name="Comp Range Bias & RX Chan Phase (Advanced)", height=80, width=500)
        self.measure_range_bias_and_rx_chan_phase_editor = JSONEditor(
            value=self.config.measure_range_bias_and_rx_chan_phase or [],
            name="Measure Range Bias & RX Chan Phase (Advanced)", height=80, width=500)
        self.aoa_fov_cfg_editor = JSONEditor(
            value=self.config.aoa_fov_cfg.model_dump() if getattr(self.config, 'aoa_fov_cfg', None) and hasattr(self.config.aoa_fov_cfg, 'model_dump') else (self.config.aoa_fov_cfg or {}),
            name="AOA FOV Config (Advanced)", height=80, width=500)
        self.cfar_fov_cfgs_editor = JSONEditor(
            value=[c.model_dump() if hasattr(c, 'model_dump') else c for c in (self.config.cfar_fov_cfgs or [])],
            name="CFAR FOV Configs (Advanced)", height=80, width=500)
        self.extended_max_velocity_editor = JSONEditor(
            value=self.config.extended_max_velocity or {},
            name="Extended Max Velocity (Advanced)", height=60, width=500)
        self.cq_rx_sat_monitor_editor = JSONEditor(
            value=self.config.cq_rx_sat_monitor or {},
            name="CQ RX Sat Monitor (Advanced)", height=60, width=500)
        self.cq_sig_img_monitor_editor = JSONEditor(
            value=self.config.cq_sig_img_monitor or {},
            name="CQ Sig Img Monitor (Advanced)", height=60, width=500)
        self.analog_monitor_editor = JSONEditor(
            value=self.config.analog_monitor or {},
            name="Analog Monitor (Advanced)", height=60, width=500)
        self.lvds_stream_cfg_editor = JSONEditor(
            value=self.config.lvds_stream_cfg or {},
            name="LVDS Stream Config (Advanced)", height=60, width=500)
        self.bpm_cfg_editor = JSONEditor(
            value=self.config.bpm_cfg or {},
            name="BPM Config (Advanced)", height=60, width=500)
        self.calib_data_editor = JSONEditor(
            value=self.config.calib_data or {},
            name="Calib Data (Advanced)", height=60, width=500)

    def _link_widgets_to_config(self):
        # Link top selectors
        self.param.watch(self._on_antenna_config_change, 'antenna_config_select')

        # Link Scene Selection sliders and inputs bidirectionally
        self.frame_rate_slider.param.watch(lambda event: setattr(self.frame_rate_input, 'value', event.new), 'value')
        self.frame_rate_input.param.watch(lambda event: setattr(self.frame_rate_slider, 'value', event.new), 'value')
        self.frame_rate_slider.param.watch(lambda event: setattr(self.config, 'frame_rate_fps', event.new), 'value')
        self.frame_rate_input.param.watch(lambda event: setattr(self.config, 'frame_rate_fps', event.new), 'value')

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

        # Expert mode advanced fields linking
        self.cfar_cfgs_editor.param.watch(lambda event: setattr(self.config, 'cfar_cfgs', event.new), 'value')
        self.calib_dc_range_sig_editor.param.watch(lambda event: setattr(self.config, 'calib_dc_range_sig', event.new), 'value')
        self.comp_range_bias_and_rx_chan_phase_editor.param.watch(lambda event: setattr(self.config, 'comp_range_bias_and_rx_chan_phase', event.new), 'value')
        self.measure_range_bias_and_rx_chan_phase_editor.param.watch(lambda event: setattr(self.config, 'measure_range_bias_and_rx_chan_phase', event.new), 'value')
        self.aoa_fov_cfg_editor.param.watch(lambda event: setattr(self.config, 'aoa_fov_cfg', event.new), 'value')
        self.cfar_fov_cfgs_editor.param.watch(lambda event: setattr(self.config, 'cfar_fov_cfgs', event.new), 'value')
        self.extended_max_velocity_editor.param.watch(lambda event: setattr(self.config, 'extended_max_velocity', event.new), 'value')
        self.cq_rx_sat_monitor_editor.param.watch(lambda event: setattr(self.config, 'cq_rx_sat_monitor', event.new), 'value')
        self.cq_sig_img_monitor_editor.param.watch(lambda event: setattr(self.config, 'cq_sig_img_monitor', event.new), 'value')
        self.analog_monitor_editor.param.watch(lambda event: setattr(self.config, 'analog_monitor', event.new), 'value')
        self.lvds_stream_cfg_editor.param.watch(lambda event: setattr(self.config, 'lvds_stream_cfg', event.new), 'value')
        self.bpm_cfg_editor.param.watch(lambda event: setattr(self.config, 'bpm_cfg', event.new), 'value')
        self.calib_data_editor.param.watch(lambda event: setattr(self.config, 'calib_data', event.new), 'value')

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

    @pn.depends('expert_mode')
    def view(self):
        # Top Configuration Section
        top_config_layout = pn.Row(
            pn.Column(
                StaticText(value="<b>Antenna Config (Azimuth Res - deg)</b>"), 
                pn.Param(self.param.antenna_config_select, widgets={ 'antenna_config_select': pn.widgets.Select}) # Use pn.Param for Selectors
            )
        )
        
        # Scene Selection Section
        scene_selection_layout = pn.Column(
            StaticText(value="<h2>Scene Selection</h2>"),
            pn.Row(self.frame_rate_slider, self.frame_rate_input, sizing_mode='stretch_width'),
            pn.Row(self.range_res_slider, self.range_res_input, sizing_mode='stretch_width'),
            pn.Row(self.max_range_slider, self.max_range_input, sizing_mode='stretch_width'),
            pn.Row(self.max_vel_slider, self.max_vel_input, sizing_mode='stretch_width'),
            pn.Row(self.radial_vel_res_label, self.radial_vel_res_select, self.radial_vel_res_numeric_display, sizing_mode='stretch_width')
        )

        # Plot Selection Section
        plot_selection_layout = pn.Column(
            StaticText(value="<h2>Plot Selection</h2>"),
            pn.Row(
                pn.Column(self.plot_scatter_cb, self.plot_range_profile_cb, self.plot_noise_profile_cb),
                pn.Column(self.plot_range_azimuth_cb, self.plot_range_doppler_cb, self.plot_statistics_cb)
            )
        )

        expert_toggle = pn.widgets.Checkbox(name="Expert Mode (show advanced parameters)", value=self.expert_mode, width=250)
        def _toggle_expert(event):
            self.expert_mode = event.new
        expert_toggle.param.watch(_toggle_expert, 'value')

        # Advanced/diagnostic section (shown only if expert_mode is True)
        advanced_section = pn.Column(
            pn.pane.Markdown("## Advanced/Diagnostic Parameters (Expert Mode)"),
            self.cfar_cfgs_editor,
            self.calib_dc_range_sig_editor,
            self.comp_range_bias_and_rx_chan_phase_editor,
            self.measure_range_bias_and_rx_chan_phase_editor,
            self.aoa_fov_cfg_editor,
            self.cfar_fov_cfgs_editor,
            self.extended_max_velocity_editor,
            self.cq_rx_sat_monitor_editor,
            self.cq_sig_img_monitor_editor,
            self.analog_monitor_editor,
            self.lvds_stream_cfg_editor,
            self.bpm_cfg_editor,
            self.calib_data_editor,
            visible=self.expert_mode
        )

        return pn.Column(
            expert_toggle,
            top_config_layout,
            pn.layout.Divider(),
            scene_selection_layout,
            pn.layout.Divider(),
            plot_selection_layout,
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
 