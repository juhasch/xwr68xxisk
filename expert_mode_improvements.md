# Expert Mode Improvements for Radar Configuration GUI

## Overview

The Expert Mode in the radar configuration GUI has been significantly improved to provide a better user experience for advanced radar parameter configuration. This document explains what the expert mode is, the problems with the original implementation, and the improvements made.

## What is Expert Mode?

Expert Mode provides access to **advanced/diagnostic parameters** that are not part of the standard user interface. These are low-level radar configuration parameters typically used by radar engineers and developers for:

### 1. Advanced Signal Processing Configuration
- **CFAR (Constant False Alarm Rate) Detection**: Window length, guard length, noise divider, threshold scaling, peak grouping
- **Multi-Object Beamforming**: Enable/disable and threshold settings
- **Angle of Arrival (AOA) FOV**: Azimuth and elevation field of view limits

### 2. Calibration and Compensation
- **DC Range Calibration**: Enable/disable, negative/positive bin indices, number of averaging frames
- **Range Bias and RX Channel Phase**: Compensation and measurement settings

### 3. Diagnostic Monitoring
- **GUI Monitor**: Detected objects display, log magnitude range, noise profile, heat maps, statistics
- **Analog Monitor**: RX saturation monitoring, signal image band monitoring
- **RX Saturation Monitor**: Advanced receiver saturation detection

### 4. Advanced Data Streaming
- **LVDS Stream Configuration**: Header enable, data format, software enable
- **BPM (Beam Pattern Monitor)**: Advanced beam pattern monitoring

## Problems with Original Implementation

### 1. Poor User Experience
- **Cryptic JSON Editors**: Parameters displayed as raw JSON with meaningless labels like "Array [0]" and "object {5}"
- **No Documentation**: No help text or descriptions for what each parameter does
- **No Validation**: No constraints or guidance on valid values or ranges
- **Generic Data Types**: Parameters stored as generic `dict` and `list` types instead of proper Pydantic models

### 2. Technical Issues
- **Fixed Modal Size**: Modal was fixed at 850x900 pixels and got clipped by browser windows
- **No Scrolling**: Content at the bottom was inaccessible
- **Poor Layout**: No organization or grouping of related parameters

### 3. Maintenance Issues
- **No Type Safety**: Generic types made it difficult to validate and maintain
- **No IDE Support**: Lack of proper types meant no autocomplete or error checking

## Improvements Made

### 1. Form-Based Parameter Editors

Replaced JSON editors with proper form controls:

#### CFAR Configuration
```python
# Before: JSON editor with cryptic data
cfar_cfgs_editor = JSONEditor(value=[...], name="CFAR Configs (Advanced)")

# After: Proper form controls
cfar_subframe_idx = IntInput(name="Subframe Index", value=-1, width=100)
cfar_proc_direction = Select(name="Processing Direction", options=["Range (0)", "Doppler (1)"], value="Range (0)", width=150)
cfar_win_len = IntSlider(name="Window Length", start=4, end=32, value=8, step=2, width=200)
cfar_threshold_scale = FloatSlider(name="Threshold Scale", start=1.0, end=50.0, value=15.0, step=0.5, width=200)
cfar_peak_grouping_en = Checkbox(name="Peak Grouping", value=False)
```

#### Calibration DC Range Signal
```python
calib_dc_enabled = Checkbox(name="Enable DC Calibration", value=False)
calib_dc_negative_bin = IntInput(name="Negative Bin Index", value=-5, width=100)
calib_dc_positive_bin = IntInput(name="Positive Bin Index", value=8, width=100)
calib_dc_num_avg_frames = IntSlider(name="Number of Avg Frames", start=1, end=512, value=256, step=1, width=200)
```

#### AOA FOV Configuration
```python
aoa_min_azimuth = FloatSlider(name="Min Azimuth (deg)", start=-90.0, end=0.0, value=-90.0, step=1.0, width=200)
aoa_max_azimuth = FloatSlider(name="Max Azimuth (deg)", start=0.0, end=90.0, value=90.0, step=1.0, width=200)
aoa_min_elevation = FloatSlider(name="Min Elevation (deg)", start=-90.0, end=0.0, value=-90.0, step=1.0, width=200)
aoa_max_elevation = FloatSlider(name="Max Elevation (deg)", start=0.0, end=90.0, value=90.0, step=1.0, width=200)
```

### 2. Proper Pydantic Model Integration

All expert mode parameters now properly integrate with the Pydantic models:

```python
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
```

### 3. Improved Modal Layout

#### Responsive Sizing
```python
self.config_modal = pn.Column(
    config_modal_header,
    self.profile_config_view_panel.view,
    config_modal_buttons,
    visible=False, 
    width=1000,  # Increased from 850
    height=800,  # Reduced from 900
    css_classes=['modal', 'modal-content'],
    styles={
        'max-height': '90vh',  # Responsive height
        'overflow-y': 'auto',  # Enable scrolling
        'overflow-x': 'hidden' # Prevent horizontal scroll
    }
)
```

#### Enhanced CSS
```css
.modal {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 1050 !important;
    max-width: 95vw !important;  /* Responsive width */
    max-height: 95vh !important; /* Responsive height */
}
.modal-content {
    background: white !important;
    border: 1px solid #ddd !important;
    border-radius: 5px !important;
    padding: 20px !important;
    box-shadow: 0 0 10px rgba(0,0,0,0.1) !important;
    overflow-y: auto !important;  /* Enable scrolling */
    overflow-x: hidden !important; /* Prevent horizontal scroll */
}
```

### 4. Organized Parameter Groups

Parameters are now organized into logical groups with clear headings:

```python
advanced_section = pn.Column(
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
    
    # ... more sections
)
```

## Benefits of the Improvements

### 1. Better User Experience
- **Intuitive Controls**: Sliders, checkboxes, and dropdowns instead of JSON
- **Clear Labels**: Descriptive names for all parameters
- **Logical Grouping**: Related parameters grouped together
- **Responsive Design**: Modal adapts to different screen sizes

### 2. Improved Maintainability
- **Type Safety**: Proper Pydantic model integration
- **Validation**: Built-in validation from Pydantic models
- **IDE Support**: Full autocomplete and error checking
- **Documentation**: Clear parameter descriptions and ranges

### 3. Enhanced Functionality
- **Real-time Updates**: Changes immediately reflected in configuration
- **Proper Defaults**: Sensible default values for all parameters
- **Range Validation**: Sliders with appropriate min/max values
- **Error Prevention**: Proper data types prevent invalid inputs

## Usage

### Enabling Expert Mode
1. Open the radar configuration modal
2. Check the "Expert Mode (show advanced parameters)" checkbox
3. Advanced parameters will appear below the standard configuration

### Parameter Categories

#### CFAR Detection Configuration
- **Subframe Index**: Which subframe to apply CFAR to (-1 for legacy mode)
- **Processing Direction**: Range (0) or Doppler (1) processing
- **Window Length**: Number of cells in the averaging window (4-32)
- **Guard Length**: Number of guard cells around the cell under test (2-16)
- **Threshold Scale**: Multiplier for the detection threshold (1.0-50.0)
- **Peak Grouping**: Enable/disable peak grouping for better detection

#### Calibration DC Range Signal
- **Enable DC Calibration**: Turn DC range calibration on/off
- **Negative/Positive Bin Indices**: Range bins for DC signal measurement
- **Number of Avg Frames**: Frames to average for calibration (1-512)

#### Angle of Arrival FOV Configuration
- **Min/Max Azimuth**: Azimuth angle limits in degrees (-90 to +90)
- **Min/Max Elevation**: Elevation angle limits in degrees (-90 to +90)

#### Multi-Object Beamforming
- **Enable MOB**: Turn multi-object beamforming on/off
- **MOB Threshold**: Detection threshold for beamforming (0.0-1.0)

#### GUI Monitor Configuration
- **Detected Objects**: Display mode (None, Objects + Side Info, Objects Only)
- **Log Magnitude Range**: Enable range profile display
- **Noise Profile**: Enable noise floor profile display
- **Heat Maps**: Enable range-azimuth and range-Doppler heat maps
- **Statistics Info**: Enable statistics display

#### Analog Monitor Configuration
- **RX Saturation Monitoring**: Monitor receiver saturation
- **Signal Image Band Monitoring**: Monitor signal image band

## Future Enhancements

### 1. Parameter Documentation
- Add tooltips with detailed parameter descriptions
- Include links to radar documentation
- Show parameter relationships and dependencies

### 2. Advanced Validation
- Cross-parameter validation (e.g., min < max for ranges)
- Real-time validation feedback
- Warning messages for potentially problematic settings

### 3. Preset Configurations
- Save/load expert mode configurations
- Pre-defined configurations for common use cases
- Import/export functionality

### 4. Visual Feedback
- Real-time parameter impact visualization
- Performance indicators for current settings
- Configuration comparison tools

## Conclusion

The expert mode improvements transform a cryptic, difficult-to-use JSON editor into an intuitive, well-organized form-based interface. The new implementation provides:

- **Better usability** through proper form controls
- **Improved maintainability** through Pydantic model integration
- **Enhanced functionality** with real-time updates and validation
- **Responsive design** that works on different screen sizes

These improvements make the advanced radar parameters accessible to users who need fine-grained control over their radar configuration while maintaining the simplicity of the standard interface for basic users. 