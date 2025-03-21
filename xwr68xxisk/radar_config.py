from typing import Dict, List, Union, Optional

class RadarCommand:
    """Base class for radar configuration commands"""
    
    def __init__(self, name: str, params: List[Union[int, float, str]]):
        self.name = name
        self.params = params
        
    def to_string(self) -> str:
        """Convert command to string format for configuration file"""
        params_str = " ".join(str(param) for param in self.params)
        return f"{self.name} {params_str}"
    
    @classmethod
    def from_string(cls, command_str: str) -> 'RadarCommand':
        """Create a command from a string"""
        parts = command_str.strip().split()
        name = parts[0]
        
        # Convert parameters to appropriate types (int/float)
        params = []
        for param in parts[1:]:
            try:
                # Try to convert to integer
                params.append(int(param))
            except ValueError:
                try:
                    # Try to convert to float
                    params.append(float(param))
                except ValueError:
                    # Keep as string if not numeric
                    params.append(param)
        
        # Find the specific command class if available
        command_classes = {
            'dfeDataOutputMode': DfeDataOutputModeCommand,
            'channelCfg': ChannelConfigCommand,
            'adcCfg': AdcConfigCommand,
            'adcbufCfg': AdcBufConfigCommand,
            'profileCfg': ProfileConfigCommand,
            'chirpCfg': ChirpConfigCommand,
            'frameCfg': FrameConfigCommand,
            'guiMonitor': GuiMonitorCommand,
            'cfarCfg': CfarConfigCommand,
            'multiObjBeamForming': MultiObjBeamFormingCommand,
            'clutterRemoval': ClutterRemovalCommand,
            'calibDcRangeSig': CalibDcRangeSigCommand,
            'aoaFovCfg': AoaFovConfigCommand,
        }
        
        if name in command_classes:
            return command_classes[name](params)
        elif name == 'sensorStop':
            cmd = SensorStopCommand(params)
            cmd.name = 'sensorStop'  # Override the name
            return cmd
        elif name == 'flushCfg':
            cmd = FlushCfgCommand(params)
            cmd.name = 'flushCfg'  # Override the name
            return cmd
        elif name == 'lowPower':
            cmd = SimpleRadarCommand(params)
            cmd.name = 'lowPower'  # Override the name
            return cmd
        
        # Default to generic command
        return cls(name, params)


class SimpleRadarCommand(RadarCommand):
    """Simple commands with no parameters or simple param lists"""
    
    def __init__(self, params: List[Union[int, float, str]] = None):
        if params is None:
            params = []
        super().__init__(self.__class__.__name__.replace('Command', ''), params)


class SensorStopCommand(SimpleRadarCommand):
    pass


class FlushCfgCommand(SimpleRadarCommand):
    pass


class DfeDataOutputModeCommand(RadarCommand):
    """Data output mode configuration"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('dfeDataOutputMode', params)
        
    @property
    def mode_type(self) -> int:
        """Get mode type (1: frame based, 2: continuous, 3: advanced frame)"""
        return self.params[0]
    
    @mode_type.setter
    def mode_type(self, value: int):
        """Set mode type (1: frame based, 2: continuous, 3: advanced frame)"""
        if value not in [1, 2, 3]:
            raise ValueError("Mode type must be 1, 2, or 3")
        self.params[0] = value


class ChannelConfigCommand(RadarCommand):
    """Channel configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('channelCfg', params)
    
    @property
    def rx_channel_en(self) -> int:
        """Receive antenna mask"""
        return self.params[0]
    
    @rx_channel_en.setter
    def rx_channel_en(self, value: int):
        self.params[0] = value
    
    @property
    def tx_channel_en(self) -> int:
        """Transmit antenna mask"""
        return self.params[1]
    
    @tx_channel_en.setter
    def tx_channel_en(self, value: int):
        self.params[1] = value
    
    @property
    def cascading(self) -> int:
        """SoC cascading"""
        return self.params[2]
    
    @cascading.setter
    def cascading(self, value: int):
        self.params[2] = value


class AdcConfigCommand(RadarCommand):
    """ADC configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('adcCfg', params)
    
    @property
    def num_adc_bits(self) -> int:
        """ADC bits (0: 12-bits, 1: 14-bits, 2: 16-bits)"""
        return self.params[0]
    
    @num_adc_bits.setter
    def num_adc_bits(self, value: int):
        if value not in [0, 1, 2]:
            raise ValueError("num_adc_bits must be 0, 1, or 2")
        self.params[0] = value
    
    @property
    def adc_output_fmt(self) -> int:
        """ADC output format (0: real, 1: complex 1x, 2: complex 2x)"""
        return self.params[1]
    
    @adc_output_fmt.setter
    def adc_output_fmt(self, value: int):
        if value not in [0, 1, 2]:
            raise ValueError("adc_output_fmt must be 0, 1, or 2")
        self.params[1] = value


class AdcBufConfigCommand(RadarCommand):
    """ADC buffer configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('adcbufCfg', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index (-1 for legacy mode)"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def adc_output_fmt(self) -> int:
        """ADC output format (0: Complex, 1: Real)"""
        return self.params[1]
    
    @adc_output_fmt.setter
    def adc_output_fmt(self, value: int):
        if value not in [0, 1]:
            raise ValueError("adc_output_fmt must be 0 or 1")
        self.params[1] = value
    
    @property
    def sample_swap(self) -> int:
        """Sample swap (0: I in LSB/Q in MSB, 1: Q in LSB/I in MSB)"""
        return self.params[2]
    
    @sample_swap.setter
    def sample_swap(self, value: int):
        if value not in [0, 1]:
            raise ValueError("sample_swap must be 0 or 1")
        self.params[2] = value
    
    @property
    def chan_interleave(self) -> int:
        """Channel interleave (0: interleaved, 1: non-interleaved)"""
        return self.params[3]
    
    @chan_interleave.setter
    def chan_interleave(self, value: int):
        if value not in [0, 1]:
            raise ValueError("chan_interleave must be 0 or 1")
        self.params[3] = value
    
    @property
    def chirp_threshold(self) -> int:
        """Threshold for buffer switch (0-8)"""
        return self.params[4]
    
    @chirp_threshold.setter
    def chirp_threshold(self, value: int):
        if not (0 <= value <= 8):
            raise ValueError("chirp_threshold must be between 0 and 8")
        self.params[4] = value


class ProfileConfigCommand(RadarCommand):
    """Profile configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('profileCfg', params)
    
    @property
    def profile_id(self) -> int:
        """Profile identifier"""
        return self.params[0]
    
    @profile_id.setter
    def profile_id(self, value: int):
        self.params[0] = value
    
    @property
    def start_freq(self) -> float:
        """Frequency start in GHz"""
        return self.params[1]
    
    @start_freq.setter
    def start_freq(self, value: float):
        self.params[1] = value
    
    @property
    def idle_time(self) -> float:
        """Idle time in μs"""
        return self.params[2]
    
    @idle_time.setter
    def idle_time(self, value: float):
        self.params[2] = value
    
    @property
    def adc_start_time(self) -> float:
        """ADC valid start time in μs"""
        return self.params[3]
    
    @adc_start_time.setter
    def adc_start_time(self, value: float):
        self.params[3] = value
    
    @property
    def ramp_end_time(self) -> float:
        """Ramp end time in μs"""
        return self.params[4]
    
    @ramp_end_time.setter
    def ramp_end_time(self, value: float):
        self.params[4] = value
    
    @property
    def freq_slope_const(self) -> float:
        """Frequency slope in MHz/μs"""
        return self.params[7]
    
    @freq_slope_const.setter
    def freq_slope_const(self, value: float):
        if value <= 0:
            raise ValueError("freq_slope_const must be greater than 0")
        self.params[7] = value
    
    @property
    def num_adc_samples(self) -> int:
        """Number of ADC samples"""
        return self.params[9]
    
    @num_adc_samples.setter
    def num_adc_samples(self, value: int):
        self.params[9] = value
    
    @property
    def dig_out_sample_rate(self) -> int:
        """ADC sampling frequency in ksps"""
        return self.params[10]
    
    @dig_out_sample_rate.setter
    def dig_out_sample_rate(self, value: int):
        self.params[10] = value
    
    @property
    def rx_gain(self) -> int:
        """RX gain in dB"""
        return self.params[13]
    
    @rx_gain.setter
    def rx_gain(self, value: int):
        self.params[13] = value


class ChirpConfigCommand(RadarCommand):
    """Chirp configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('chirpCfg', params)
    
    @property
    def start_idx(self) -> int:
        """Start index of chirp"""
        return self.params[0]
    
    @start_idx.setter
    def start_idx(self, value: int):
        self.params[0] = value
    
    @property
    def end_idx(self) -> int:
        """End index of chirp"""
        return self.params[1]
    
    @end_idx.setter
    def end_idx(self, value: int):
        self.params[1] = value
    
    @property
    def tx_antenna_mask(self) -> int:
        """TX antenna mask for this chirp"""
        return self.params[7]
    
    @tx_antenna_mask.setter
    def tx_antenna_mask(self, value: int):
        self.params[7] = value


class FrameConfigCommand(RadarCommand):
    """Frame configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('frameCfg', params)
    
    @property
    def start_idx(self) -> int:
        """Index of first chirp in frame"""
        return self.params[0]
    
    @start_idx.setter
    def start_idx(self, value: int):
        self.params[0] = value
    
    @property
    def end_idx(self) -> int:
        """Index of last chirp in frame"""
        return self.params[1]
    
    @end_idx.setter
    def end_idx(self, value: int):
        self.params[1] = value
    
    @property
    def num_loops(self) -> int:
        """Number of chirp loops per frame"""
        return self.params[2]
    
    @num_loops.setter
    def num_loops(self, value: int):
        self.params[2] = value
    
    @property
    def num_frames(self) -> int:
        """Number of frames to emit (0 for infinite)"""
        return self.params[3]
    
    @num_frames.setter
    def num_frames(self, value: int):
        self.params[3] = value
    
    @property
    def frame_period_ms(self) -> float:
        """Frame period in milliseconds"""
        return self.params[4]
    
    @frame_period_ms.setter
    def frame_period_ms(self, value: float):
        self.params[4] = value


class GuiMonitorCommand(RadarCommand):
    """GUI monitoring configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('guiMonitor', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def detected_objects(self) -> int:
        """Detected objects (0: None, 1: Objects+info, 2: Objects only)"""
        return self.params[1]
    
    @detected_objects.setter
    def detected_objects(self, value: int):
        if value not in [0, 1, 2]:
            raise ValueError("detected_objects must be 0, 1, or 2")
        self.params[1] = value


class CfarConfigCommand(RadarCommand):
    """CFAR detection configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('cfarCfg', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def proc_direction(self) -> int:
        """Processing direction (0: range, 1: doppler)"""
        return self.params[1]
    
    @proc_direction.setter
    def proc_direction(self, value: int):
        if value not in [0, 1]:
            raise ValueError("proc_direction must be 0 or 1")
        self.params[1] = value


class MultiObjBeamFormingCommand(RadarCommand):
    """Multi-object beamforming configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('multiObjBeamForming', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def enabled(self) -> int:
        """Enable/disable multi-object beamforming"""
        return self.params[1]
    
    @enabled.setter
    def enabled(self, value: int):
        if value not in [0, 1]:
            raise ValueError("enabled must be 0 or 1")
        self.params[1] = value
    
    @property
    def threshold(self) -> float:
        """Detection threshold"""
        return self.params[2]
    
    @threshold.setter
    def threshold(self, value: float):
        self.params[2] = value


class ClutterRemovalCommand(RadarCommand):
    """Clutter removal configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('clutterRemoval', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def enabled(self) -> int:
        """Enable/disable clutter removal"""
        return self.params[1]
    
    @enabled.setter
    def enabled(self, value: int):
        if value not in [0, 1]:
            raise ValueError("enabled must be 0 or 1")
        self.params[1] = value


class CalibDcRangeSigCommand(RadarCommand):
    """DC range calibration configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('calibDcRangeSig', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def enabled(self) -> int:
        """Enable/disable calibration"""
        return self.params[1]
    
    @enabled.setter
    def enabled(self, value: int):
        if value not in [0, 1]:
            raise ValueError("enabled must be 0 or 1")
        self.params[1] = value


class AoaFovConfigCommand(RadarCommand):
    """Angle of Arrival Field of View configuration command"""
    
    def __init__(self, params: List[Union[int, float, str]]):
        super().__init__('aoaFovCfg', params)
    
    @property
    def subframe_idx(self) -> int:
        """Subframe index"""
        return self.params[0]
    
    @subframe_idx.setter
    def subframe_idx(self, value: int):
        self.params[0] = value
    
    @property
    def min_azimuth_deg(self) -> float:
        """Minimum azimuth in degrees"""
        return self.params[1]
    
    @min_azimuth_deg.setter
    def min_azimuth_deg(self, value: float):
        self.params[1] = value
    
    @property
    def max_azimuth_deg(self) -> float:
        """Maximum azimuth in degrees"""
        return self.params[2]
    
    @max_azimuth_deg.setter
    def max_azimuth_deg(self, value: float):
        self.params[2] = value
    
    @property
    def min_elevation_deg(self) -> float:
        """Minimum elevation in degrees"""
        return self.params[3]
    
    @min_elevation_deg.setter
    def min_elevation_deg(self, value: float):
        self.params[3] = value
    
    @property
    def max_elevation_deg(self) -> float:
        """Maximum elevation in degrees"""
        return self.params[4]
    
    @max_elevation_deg.setter
    def max_elevation_deg(self, value: float):
        self.params[4] = value


class RadarConfig:
    """Main class for radar configuration management"""
    
    def __init__(self, name: str = None):
        self.name = name
        self.commands: List[RadarCommand] = []
        
    @classmethod
    def from_string(cls, config_str: str, name: str = None) -> 'RadarConfig':
        """Create a radar configuration from a multiline string"""
        config = cls(name)
        
        # Parse each non-empty line
        for line in config_str.strip().split('\n'):
            line = line.strip()
            if line:
                config.commands.append(RadarCommand.from_string(line))
        
        return config
    
    @classmethod
    def from_file(cls, file_path: str, name: str = None) -> 'RadarConfig':
        """Create a radar configuration from a .cfg file
        
        Args:
            file_path: Path to the .cfg file
            name: Optional name for the configuration
            
        Returns:
            RadarConfig object created from the file
        """
        with open(file_path, 'r') as f:
            config_str = f.read()
        
        # Use the filename as name if not provided
        if name is None:
            import os
            name = os.path.splitext(os.path.basename(file_path))[0]
            
        config = cls.from_string(config_str)
        config.name = name  # Ensure name is set correctly
        return config
    
    def to_string(self) -> str:
        """Convert configuration to a multiline string"""
        return '\n'.join(cmd.to_string() for cmd in self.commands)
    
    def to_file(self, file_path: str) -> None:
        """Save the configuration to a .cfg file
        
        Args:
            file_path: Path where to save the configuration
        """
        with open(file_path, 'w') as f:
            f.write(self.to_string())
    
    def get_command(self, command_name: str, index: int = 0) -> Optional[RadarCommand]:
        """Get a specific command by name and optional index
        
        Args:
            command_name: The name of the command to find
            index: If multiple commands with same name exist, get the nth one (0-based)
        
        Returns:
            The command object if found, otherwise None
        """
        matches = [cmd for cmd in self.commands if cmd.name == command_name]
        if index < len(matches):
            return matches[index]
        return None
    
    def get_commands(self, command_name: str) -> List[RadarCommand]:
        """Get all commands with a specific name
        
        Args:
            command_name: The name of the commands to find
            
        Returns:
            List of matching command objects
        """
        return [cmd for cmd in self.commands if cmd.name == command_name]
    
    def add_command(self, command: RadarCommand) -> None:
        """Add a command to the configuration"""
        self.commands.append(command)
    
    def remove_command(self, command_name: str, index: int = 0) -> bool:
        """Remove a command by name and optional index
        
        Args:
            command_name: Name of the command to remove
            index: If multiple commands with same name exist, remove the nth one (0-based)
            
        Returns:
            True if command was removed, False if not found
        """
        matches = [i for i, cmd in enumerate(self.commands) if cmd.name == command_name]
        if index < len(matches):
            del self.commands[matches[index]]
            return True
        return False
    
    def update_frame_period(self, period_ms: float) -> bool:
        """Update the frame period in the configuration
        
        Args:
            period_ms: Frame period in milliseconds
            
        Returns:
            True if frame configuration was updated, False if not found
        """
        frame_cmd = self.get_command('frameCfg')
        if frame_cmd:
            frame_cmd.params[4] = period_ms
            return True
        return False
    
    def set_tx_antennas(self, tx_antenna_mask: int) -> bool:
        """Set the transmit antenna mask
        
        Args:
            tx_antenna_mask: Bitmask of TX antennas to enable
            
        Returns:
            True if channel config was updated, False if not found
        """
        channel_cmd = self.get_command('channelCfg')
        if channel_cmd:
            channel_cmd.params[1] = tx_antenna_mask
            return True
        return False
    
    def set_rx_antennas(self, rx_antenna_mask: int) -> bool:
        """Set the receive antenna mask
        
        Args:
            rx_antenna_mask: Bitmask of RX antennas to enable
            
        Returns:
            True if channel config was updated, False if not found
        """
        channel_cmd = self.get_command('channelCfg')
        if channel_cmd:
            channel_cmd.params[0] = rx_antenna_mask
            return True
        return False
    
    def set_profile_parameters(self, start_freq: float = None,
                             idle_time: float = None,
                             freq_slope: float = None,
                             adc_samples: int = None,
                             rx_gain: int = None) -> bool:
        """Update profile configuration parameters
        
        Args:
            start_freq: Start frequency in GHz
            idle_time: Idle time in μs
            freq_slope: Frequency slope in MHz/μs
            adc_samples: Number of ADC samples 
            rx_gain: RX gain in dB
            
        Returns:
            True if profile config was updated, False if not found
        """
        profile_cmd = self.get_command('profileCfg')
        if not profile_cmd:
            return False
            
        if start_freq is not None:
            profile_cmd.params[1] = start_freq
        if idle_time is not None:
            profile_cmd.params[2] = idle_time
        if freq_slope is not None:
            profile_cmd.params[7] = freq_slope
        if adc_samples is not None:
            profile_cmd.params[9] = adc_samples
        if rx_gain is not None:
            profile_cmd.params[13] = rx_gain
            
        return True
    
    def set_clutter_removal(self, enabled: bool) -> bool:
        """Enable or disable clutter removal
        
        Args:
            enabled: True to enable, False to disable
            
        Returns:
            True if clutter removal config was updated, False if not found
        """
        clutter_cmd = self.get_command('clutterRemoval')
        if clutter_cmd:
            clutter_cmd.params[1] = 1 if enabled else 0
            return True
        return False
        
    def clone(self) -> 'RadarConfig':
        """Create a copy of this configuration
        
        Returns:
            A new RadarConfig object with the same commands
        """
        import copy
        new_config = RadarConfig(self.name)
        new_config.commands = copy.deepcopy(self.commands)
        return new_config


# Create predefined configurations
def create_awr2544_config() -> RadarConfig:
    """Create AWR2544 radar configuration"""
    from defaultconfig import awr2544_str
    return RadarConfig.from_string(awr2544_str, "awr2544")


def create_xwr68xx_config() -> RadarConfig:
    """Create XWR68XX radar configuration"""
    from defaultconfig import xwr68xx_str
    return RadarConfig.from_string(xwr68xx_str, "xwr68xx") 