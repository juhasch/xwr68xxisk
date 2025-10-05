"""
Base module for TI mmWave radar sensors.

This module provides base class for XWR68xx series radar sensors using USB communication.
"""

import serial
import serial.tools.list_ports
import numpy as np
import time
from collections import deque
from typing import Tuple, Optional, List
import logging
import os
import threading
import yaml
import zmq  # type: ignore


logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_CONTROL_ENDPOINT = "tcp://127.0.0.1:5557"
DEFAULT_BRIDGE_DATA_ENDPOINT = "tcp://127.0.0.1:5556"


class RadarConnectionError(Exception):
    """Custom exception for radar connection errors."""
    pass


class RadarConnection:
    """Base class for TI XWR68xx radar sensors."""
    
    CP2105_VENDOR_ID = 0x10C4
    CP2105_PRODUCT_ID = 0xEA70
    
    MAX_BUFFER_SIZE = 2**15
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    MAGIC_WORD_LENGTH = 8
    CLI_PROMPTS = {"mmwDemo:/>"}
    
    def __init__(self):
        """Initialize RadarConnection instance."""
        self.cli_port: Optional[serial.Serial] = None
        self.data_port: Optional[serial.Serial] = None
        self.transport: str = 'serial'
        self.profile = ""
        self.version_info = None
        self.serial_number = None
        self.device_type = 'CP2105'
        self.is_running = False
        self._clutter_removal = False

        self.mob_enabled = False
        self.mob_threshold = 0.5
        
        self._detected_cli_port = None
        self._detected_data_port = None
        
        self.byte_buffer = np.zeros(self.MAX_BUFFER_SIZE, dtype='uint8')
        self.byte_buffer_length = 0
        self.current_index = 0
        self.radar_params = None
        self.reader = None
        self.missed_frames = 0
        self.total_frames = 0
        self.invalid_packets = 0
        self.failed_reads = 0
        # Ground-truth frame rate; everything else derives from this
        self.frame_rate_fps: float = 10.0
        
        # Frame counting and stopping
        self._num_frames: int = 0  # 0 means infinite frames
        self.frames_received: int = 0

        # Serialize CLI access across threads to avoid interleaved command/response pairs
        self._cli_lock = threading.RLock()

    def _normalize_response_lines(self, response: List[str]) -> List[str]:
        return [line.strip() for line in response if line and line.strip()]

    def _response_contains_done(self, response: List[str]) -> bool:
        return any(line.lower() == 'done' for line in self._normalize_response_lines(response))

    def _response_prompt_only(self, response: List[str]) -> bool:
        lines = self._normalize_response_lines(response)
        return len(lines) == 1 and lines[0] in self.CLI_PROMPTS

    @property
    def frame_period(self) -> float:
        """Get the frame period in milliseconds."""
        # Ground truth: fps set on the radar (via frameCfg). Period derives from fps.
        return 1000.0 / self.frame_rate_fps if self.frame_rate_fps > 0 else 0.0

    @frame_period.setter
    def frame_period(self, value: float) -> None:
        """Set the frame period in milliseconds."""
        self.radar_params['framePeriod'] = value

    @property
    def clutterRemoval(self) -> bool:
        """Get the static clutter removal setting."""
        return self._clutter_removal

    @clutterRemoval.setter
    def clutterRemoval(self, value: bool) -> None:
        """Set the static clutter removal setting."""
        self._clutter_removal = value
        self.send_command('clutterRemoval -1 ' + ('1' if value else '0') + '\n')

    def set_mob_enabled(self, enabled: bool) -> None:
        """Enable or disable multi-object beamforming."""
        value = '1' if enabled else '0'
        self.send_command(f'multiObjBeamForming -1 {value} 0.5\n')
        self.mob_enabled = enabled

    def set_mob_threshold(self, threshold: float) -> None:
        """Set the multi-object beamforming threshold."""
        threshold = max(0.0, min(1.0, threshold))
        self.send_command(f'multiObjBeamForming -1 1 {threshold:.2f}\n')
        self.mob_threshold = threshold

    def set_num_frames(self, num_frames: int) -> None:
        """Deprecated: use the num_frames property instead."""
        self.num_frames = num_frames

    @property
    def num_frames(self) -> int:
        """Number of frames to receive before stopping (0 = infinite)."""
        return self._num_frames

    @num_frames.setter
    def num_frames(self, value: int) -> None:
        if value is None:
            value = 0
        if value < 0:
            raise ValueError("Number of frames must be non-negative")
        self._num_frames = int(value)
        if isinstance(self.radar_params, dict):
            self.radar_params['num_frames'] = self._num_frames
        if self._num_frames > 0:
            logger.info(f"Configured to receive {self._num_frames} frames before stopping")
        else:
            logger.info("Configured for infinite frame reception")

    def reset_frame_count(self) -> None:
        """Reset the received frames counter."""
        self.frames_received = 0

    def should_stop_for_frame_count(self) -> bool:
        """Return True if the acquisition should stop based on num_frames."""
        return self.num_frames > 0 and self.frames_received >= self.num_frames

    def find_serial_ports(self, serial_number: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Find the radar ports for Silicon Labs CP2105 device."""
        ports = serial.tools.list_ports.comports()
        cli_port_path = None
        data_port_path = None
        
        for port in ports:
            if port.vid == self.CP2105_VENDOR_ID and port.pid == self.CP2105_PRODUCT_ID:
                logger.debug(f"Found CP2105 port: {port.description}")
                device_path = port.device
                
                if device_path.startswith('/dev/cu.usbserial'):
                    device_path = device_path.replace('/dev/cu.usbserial', '/dev/tty.usbserial')
                
                # Handle different naming conventions based on OS
                if "usbserial" in device_path:
                    if device_path.endswith("0"):
                        cli_port_path = device_path
                    elif device_path.endswith("1"):
                        data_port_path = device_path
                    else:
                        cli_port_path = device_path
                    self.serial_number = port.serial_number
                elif "SLAB_USBtoUART" in device_path:  # macOS
                    if device_path.endswith('UART'):
                        data_port_path = device_path
                    else:
                        cli_port_path = device_path
                    self.serial_number = port.serial_number
                elif "Enhanced" in port.description:
                    cli_port_path = device_path
                elif "Standard" in port.description:
                    data_port_path = device_path
                    self.serial_number = port.serial_number
                    
                if serial_number and serial_number != self.serial_number:
                    data_port_path = None
                    cli_port_path = None
        
        if cli_port_path and data_port_path:
            logger.info(f"Found CLI port: {cli_port_path}")
            logger.info(f"Found Data port: {data_port_path}")
            logger.info(f"Serial number: {self.serial_number}")
        
        return cli_port_path, data_port_path

    def detect_radar_type(self) -> str:
        """Detect which type of radar is connected and return its type."""
        if not (self._detected_cli_port and self._detected_data_port):
            self._detected_cli_port, self._detected_data_port = self.find_serial_ports()
        
        if self._detected_cli_port and self._detected_data_port:
            logger.info("Detected XWR68xx radar via CP2105 interface")
            return "xwr68xx"
            
        return None, None


    def _read_cli_response(self, timeout_ms: float = 100.0):
        """Read and return the complete response from the CLI port with optimized timing.
        
        Args:
            timeout_ms: Maximum time to wait for complete response in milliseconds
        """
        response = []
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000.0
        
        # First, do rapid polling for immediate responses
        rapid_poll_duration = min(0.01, timeout_seconds / 4)  # Poll rapidly for first 10ms or 1/4 of timeout
        rapid_poll_end = start_time + rapid_poll_duration
        
        while time.time() < rapid_poll_end:
            if self.cli_port.in_waiting:
                break
            time.sleep(0.0001)  # 0.1ms sleep for rapid polling
        
        # Now read all available data with normal polling
        last_data_time = time.time()
        idle_timeout = 0.005  # 5ms idle timeout between chunks
        
        while time.time() - start_time < timeout_seconds:
            if self.cli_port.in_waiting:
                # Read all available data
                while self.cli_port.in_waiting:
                    try:
                        line = self.cli_port.readline().decode('utf-8').strip()
                        if line:
                            response.append(line)
                            last_data_time = time.time()
                            
                            # Check for command completion
                            if line == "mmwDemo:/>" or "Error" in line:
                                return response
                    except Exception as e:
                        logger.debug(f"Error reading CLI response: {e}")
                        break
            else:
                # No data available - check if we should keep waiting
                if response and (time.time() - last_data_time > idle_timeout):
                    # We have some response and haven't seen data for idle_timeout
                    # Assume response is complete
                    break
                    
                # Short sleep before next check
                time.sleep(0.0005)  # 0.5ms sleep
                
        if not response:
            logger.warning(f"No response from sensor after {timeout_ms}ms")
        elif response and response[-1] != "mmwDemo:/>":
            logger.debug(f"Response may be incomplete (no prompt): {response}")
            
        return response

    def send_command(self, command: str, ignore_response: bool = False, timeout_ms: float = None) -> None:
        """Send a command to the radar and verify responses.
        
        Args:
            command: Command to send to the radar.
            ignore_response: If True, do not wait for a response from the radar.
            timeout_ms: Timeout in milliseconds. If None, uses adaptive timeout based on command type.
        """
        # Determine optimal timeout based on command type if not specified
        if timeout_ms is None:
            if command.startswith('sensorStart'):
                timeout_ms = 200.0  # Sensor start can take longer
            elif command.startswith('sensorStop'):
                timeout_ms = 100.0  # Sensor stop is usually quick
            elif command.startswith(('profileCfg', 'frameCfg', 'chirpCfg')):
                timeout_ms = 150.0  # Configuration commands
            elif command.startswith(('version', 'get')):
                timeout_ms = 200.0  # Query commands might take longer
            else:
                timeout_ms = 50.0   # Most commands are fast
        
        with self._cli_lock:
            self.cli_port.write(f"{command}\n".encode())
            logger.debug(f"Sending command: {command}")
            
            if not ignore_response:
                response = self._read_cli_response(timeout_ms)
                if response:
                    has_error = False
                    for line in response:
                        if "Error" in line and not (
                            "Debug:" in line or
                            "PHY" in line or
                            "Ignored:" in line
                        ):
                            has_error = True
                            break
                    
                    if has_error:
                        logger.error(f"Error in command '{command}': {response}")
                        raise RadarConnectionError(f"Configuration error: {response}")
                    logger.debug(f"Response: {response}")

    def send_commands_batch(self, commands: List[str], timeout_ms_per_command: float = 50.0) -> List[str]:
        """Send multiple commands with optimized timing.
        
        Args:
            commands: List of commands to send
            timeout_ms_per_command: Timeout per command in milliseconds
            
        Returns:
            List of responses for each command
        """
        responses = []
        
        for i, command in enumerate(commands):
            # Use shorter timeout for batch operations
            timeout = timeout_ms_per_command
            
            # Special handling for certain commands
            if command.startswith('sensorStart'):
                timeout = 200.0
            elif command.startswith('sensorStop'):
                timeout = 100.0
                
            try:
                self.send_command(command, timeout_ms=timeout)
                responses.append("Done")
            except Exception as e:
                logger.error(f"Failed on command {i+1}/{len(commands)}: {command}")
                responses.append(f"Error: {str(e)}")
                
        return responses

    def get_version(self):
        """Get version information from the sensor."""
        if not self.is_connected():
            logger.error("Radar not connected")
            return None
        try:
            with self._cli_lock:
                self.cli_port.flushInput()
                self.cli_port.write(b'version\n')
                time.sleep(0.05)
                response_lines = self._read_cli_response()
            
            if response_lines:
                if response_lines[-1] == "mmwDemo:/>":
                    return response_lines[:-1]
                return response_lines
            return None
        except Exception as e:
            logger.error(f"Error getting version: {e}")
            return None

    def connect(self, config: str, serial_number: Optional[str] = None) -> None:
        """Connect to the radar sensor.
        
        Args:
            config: Configuration string or path to a configuration file.
            serial_number: Optional[str] = None - Serial number of the radar to connect to.
        """
        try:
            self._connect_device(serial_number)
            
            if config and os.path.isfile(config):
                logger.info(f"Reading configuration from file: {config}")
                with open(config, 'r') as f:
                    self.profile = f.read()
            else:
                logger.info("Using supplied configuration")
                self.profile = config
            
            if self.profile:
                profile_lines = [line.strip() for line in self.profile.split('\n') if line.strip()]
                self.radar_params = self.parse_configuration(profile_lines)
                logger.info("Parsed radar parameters from loaded profile during connect.")
            else:
                logger.warning("No profile content to parse radar parameters from during connect.")
                self.radar_params = self.parse_configuration([])
                logger.info("Initialized radar_params with defaults during connect.")

            self.version_info = self.get_version()
            
            if self.version_info is None:
                logger.warning("No version information received from sensor, but proceeding.")
                
        except serial.SerialException as e:
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")
            
        except Exception as e:
            logger.exception(f"Unexpected error during radar connection process:")
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")

    def set_frame_period(self, period_ms: float) -> None:
        """Set the frame period in milliseconds.
        
        Args:
            period_ms: Frame period in milliseconds.

        Somehow, we need to send a complete profile to the radar to set the frame period.
        """
        if not self.is_connected():
            logger.error("Radar not connected")
            return
            
        try:
            self.frame_period = period_ms
            self.cli_port.write(b'\n')
            time.sleep(0.05)
            self.send_command('sensorStop')
            self.configure_and_start()
            logger.info(f"Frame period set to {period_ms}ms")
        except Exception as e:
            logger.error(f"Error setting frame period: {e}")

    def parse_configuration(self, config_lines: List[str]) -> dict:
        """Parse configuration lines and extract radar parameters."""
        config_params = {}
        
        yaml_config_path = 'configs/default_config.yaml'
        if os.path.exists(yaml_config_path):
            try:
                with open(yaml_config_path, 'r') as f:
                    yaml_config = yaml.safe_load(f)
                    processing_cfg = yaml_config.get('processing', {}) if yaml_config else {}
                    config_params['clutterRemoval'] = processing_cfg.get('clutter_removal', False)
                    # Single source of truth: frame_rate_fps. Default to 10 if not present.
                    fps = processing_cfg.get('frame_rate_fps', 10.0)
                    self.frame_rate_fps = float(fps)
                    # Keep a copy in params for consumers expecting framePeriod
                    config_params['framePeriod'] = 1000.0 / self.frame_rate_fps if self.frame_rate_fps > 0 else 0.0
                    # Other processing flags
                    config_params['mobEnabled'] = processing_cfg.get('mob_enabled', False)
                    config_params['mobThreshold'] = processing_cfg.get('mob_threshold', 0.5)
            except Exception as e:
                logger.warning(f"Failed to load YAML config: {e}")
        
        for line in config_lines:
            if not line or line.startswith('%'):
                continue
                
            parts = line.split()
            if not parts:
                continue
                
            cmd = parts[0]
            args = parts[1:]
            
            try:
                if cmd == 'channelCfg':
                    config_params['rxAnt'] = bin(int(args[0])).count("1")
                    config_params['txAnt'] = bin(int(args[1])).count("1")
                    
                elif cmd == 'profileCfg':
                    config_params['samples'] = int(args[9])  # ADC samples at index 9
                    config_params['sampleRate'] = int(args[10])  # Sample rate at index 10
                    config_params['slope'] = float(args[7])  # Frequency slope at index 7
                    
                elif cmd == 'frameCfg':
                    start_chirp = int(args[0])
                    end_chirp = int(args[1])
                    num_loops = int(args[2])
                    num_frames = int(args[3])  # Number of frames (0 for infinite)
                    chirps_per_frame = (end_chirp - start_chirp + 1) * num_loops
                    config_params['chirpsPerFrame'] = chirps_per_frame
                    config_params['num_frames'] = num_frames  # Store for frame counting
                    # Update fps from profile's frame period so ground truth matches sensor
                    period_from_cfg = float(args[4])
                    self.frame_rate_fps = 1000.0 / period_from_cfg if period_from_cfg > 0 else self.frame_rate_fps
                    config_params['framePeriod'] = period_from_cfg
                    # Set num_doppler_bins based on the number of loops
                    config_params['num_doppler_bins'] = num_loops
                    logger.debug(f"FrameCfg: start={start_chirp}, end={end_chirp}, loops={num_loops}, num_frames={num_frames}, chirpsPerFrame={chirps_per_frame}, num_doppler_bins={config_params['num_doppler_bins']}")
                    
                elif cmd == 'multiObjBeamForming':
                    if len(args) >= 3:
                        if 'mobEnabled' not in config_params:
                            self.mob_enabled = int(args[1]) == 1
                            self.mob_threshold = float(args[2])
                            config_params['mobEnabled'] = self.mob_enabled
                            config_params['mobThreshold'] = self.mob_threshold
                        
                elif cmd == 'clutterRemoval':
                    if len(args) >= 2:
                        if 'clutterRemoval' not in config_params:
                            self._clutter_removal = int(args[1]) == 1
                            config_params['clutterRemoval'] = self._clutter_removal
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing configuration line '{line}': {e}")
                continue
        
        # Parse range resolution from profile comments
        for line in config_lines:
            if line.startswith('%') and 'Range resolution' in line and 'm/bin' in line:
                logger.info(f"Found range resolution line: {line.strip()}")
                try:
                    # Extract range resolution value from comment line
                    # Format: "% Range resolution (meter per 1D-FFT bin)   m/bin    0.044"
                    parts = line.split()
                    logger.info(f"Line parts: {parts}")
                    for i, part in enumerate(parts):
                        if part == 'm/bin' and i + 1 < len(parts):
                            range_resolution = float(parts[i + 1])
                            config_params['rangeStep'] = range_resolution
                            logger.info(f"Extracted range resolution from profile: {range_resolution} m/bin")
                            break
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing range resolution from line '{line}': {e}")
                break
        
        if 'samples' in config_params:
            # Range bins should equal the number of ADC samples
            config_params['rangeBins'] = config_params['samples']
        
        # Only calculate rangeStep if not already extracted from profile comments
        if 'rangeStep' not in config_params and all(k in config_params for k in ['sampleRate', 'slope', 'samples']):
            # For FMCW radar: rangeStep = (c * sampleRate) / (2 * slope * numADCSamples)
            # All values in MHz or Msps, so units are consistent
            c = 3e8  # Speed of light in m/s
            sample_rate_msps = config_params['sampleRate'] * 1e-3 # Convert ksps to Msps
            slope_mhz_us = config_params['slope']              # MHz/us
            
            # Bandwidth = slope * ADC sampling time
            # ADC sampling time = num_adc_samples / sample_rate
            adc_sampling_time_us = config_params['samples'] / (config_params['sampleRate'] * 1e-3) # us
            bandwidth_ghz = slope_mhz_us * adc_sampling_time_us * 1e-3 # GHz
            
            # Range resolution = c / (2 * Bandwidth)
            range_resolution = c / (2 * bandwidth_ghz * 1e9)
            
            config_params['rangeStep'] = range_resolution
            logger.info(f"Bandwidth: {bandwidth_ghz*1e3:.2f} MHz")
            logger.info(f"Calculated range resolution: {config_params['rangeStep']:.6f} m/bin")
        
        if 'rangeStep' in config_params and 'rangeBins' in config_params:
            config_params['maxRange'] = config_params['rangeStep'] * config_params['rangeBins']
            logger.info(f"Final rangeStep: {config_params['rangeStep']:.6f} m/bin, maxRange: {config_params['maxRange']:.2f} m")
        else:
            logger.warning("rangeStep not found in config_params")
            # Use default values from profile
            config_params['rangeStep'] = 0.044  # m/bin (from profile)
            config_params['maxRange'] = config_params['rangeStep'] * config_params.get('rangeBins', 256)
            logger.info(f"Using profile rangeStep: {config_params['rangeStep']:.6f} m/bin, maxRange: {config_params['maxRange']:.2f} m")
        
        # Set radar instance parameters from config
        if 'clutterRemoval' in config_params:
            self._clutter_removal = config_params['clutterRemoval']
        if 'mobEnabled' in config_params:
            self.mob_enabled = config_params['mobEnabled']
        if 'mobThreshold' in config_params:
            self.mob_threshold = config_params['mobThreshold']
        
        # Set number of frames from configuration if present
        cfg_num_frames = config_params.get('num_frames')
        if isinstance(cfg_num_frames, (int, float)):
            self.num_frames = int(cfg_num_frames)
        
        logger.info(f"Final radar parameters: {config_params}")
        return config_params

    def _format_radar_params(self, params: dict) -> str:
        """Format radar parameters for pretty printing."""
        groups = {
            'Antenna Configuration': ['rxAnt', 'txAnt'],
            'Sampling Parameters': ['samples', 'sampleRate', 'slope'],
            'Frame Configuration': ['chirpsPerFrame', 'rangeBins'],
            'Range Parameters': ['rangeStep', 'maxRange']
        }
        
        formatted_lines = []
        for group_name, param_names in groups.items():
            group_params = {k: params[k] for k in param_names if k in params}
            if group_params:
                formatted_lines.append(f"\n{group_name}:")
                for param_name, value in group_params.items():
                    formatted_value = f"{value:.2f}" if isinstance(value, float) else str(value)
                    formatted_lines.append(f"  {param_name:20} = {formatted_value}")
        
        return "\n".join(formatted_lines)

    def send_profile(self, ignore_response: bool = False) -> None:
        """Send the profile to the radar efficiently."""
        with self._cli_lock:
            self.cli_port.flushInput()
            
            if self.profile is None:
                raise RadarConnectionError("No radar profile available. Please load a profile before sending.")
                
            profile_lines = [line.strip() for line in self.profile.split('\n') if line.strip()]

            if self.radar_params is None:
                self.radar_params = self.parse_configuration(profile_lines)
        
            init_commands = [
                'sensorStop',
                'flushCfg'
            ]
            
            ordered_commands = {
                'init': init_commands,
                'dfe': [],
                'channel': [],
                'adc': [],
                'other': []
            }
            
            for line in profile_lines:
                if not line or line.startswith('%') or line.startswith('sensorStart'):
                    continue

                if line.startswith('clutterRemoval'):
                    line = 'clutterRemoval -1 ' + ('1' if self.radar_params['clutterRemoval'] else '0') + '\n'
                    self._clutter_removal = self.radar_params['clutterRemoval']

                if line.startswith('frameCfg'):
                    # Use configured num_frames and ground-truth fps to set frameCfg
                    # frameCfg <start_idx> <end_idx> <num_loops> <num_frames> <period_ms> <trigger_sel> <trigger_delay_ms>
                    parts = line.split()
                    # Set num_frames at parts[4]
                    if len(parts) > 4:
                        parts[4] = str(int(self.num_frames))
                    # Set period at parts[5]
                    if len(parts) > 5:
                        desired_period_ms = int(round(1000.0 / self.frame_rate_fps)) if self.frame_rate_fps > 0 else int(float(parts[5]))
                        parts[5] = str(desired_period_ms)
                    line = ' '.join(parts)

                if line.startswith('multiObjBeamForming'):
                    line = 'multiObjBeamForming -1 ' + ('1' if self.radar_params['mobEnabled'] else '0') + ' ' + str(self.radar_params['mobThreshold']) + '\n'
                    self.mob_enabled = self.radar_params['mobEnabled']
                    self.mob_threshold = self.radar_params['mobThreshold']

                parts = line.split()
                if not parts:
                    continue
                    
                cmd_type = parts[0]
                
                if cmd_type == 'dfeDataOutputMode':
                    ordered_commands['dfe'].append(line)
                elif cmd_type == 'channelCfg':
                    ordered_commands['channel'].append(line)
                elif cmd_type == 'adcCfg':
                    ordered_commands['adc'].append(line)
                elif cmd_type not in ['sensorStop', 'flushCfg']:
                    ordered_commands['other'].append(line)
            
            for group in ['init', 'dfe', 'channel', 'adc', 'other']:
                for command in ordered_commands[group]:
                    logger.debug(f"Sending command: {command}")
                    self.cli_port.write(f"{command}\n".encode())
                    if not ignore_response:
                        response = self._read_cli_response()
                        if response:
                            if self._response_contains_done(response):
                                logger.debug(f"Response: {response}")
                                continue

                            if self._response_prompt_only(response):
                                logger.debug(
                                    "Command '%s' returned prompt only; treating as success",
                                    command,
                                )
                                continue

                            response_text = ' '.join(response)
                            # Check if this is an unsupported command error
                            if "is not recognized as a CLI command" in response_text:
                                cmd_name = command.split()[0] if command.split() else "unknown"
                                logger.warning(
                                    "Command '%s' is not supported by this firmware version. Skipping command: %s",
                                    cmd_name,
                                    command,
                                )
                                logger.debug(f"Response: {response}")
                            else:
                                logger.error(f"Error in command '{command}': {response}")
                                raise RadarConnectionError(f"Configuration error: {response}")
            
            baudrate = self.data_port_baudrate
            logger.debug(f"Configuring data port with baudrate: {baudrate}")
            self.cli_port.write(f"configDataPort {baudrate} 0\n".encode())
            if not ignore_response:
                response = self._read_cli_response()
                if response:
                    if self._response_contains_done(response):
                        logger.debug(f"Data port configuration response: {response}")
                    elif self._response_prompt_only(response):
                        logger.debug("Data port config returned prompt only; treating as success")
                    else:
                        logger.error(f"Error configuring data port: {response}")
                        raise RadarConnectionError(f"Data port configuration error: {response}")

    def _connect_device(self, serial_number: Optional[str] = None) -> None:
        """Connect to the radar device."""
        if not (self._detected_cli_port and self._detected_data_port):
            self._detected_cli_port, self._detected_data_port = self.find_serial_ports(serial_number)
        
        if not (self._detected_cli_port and self._detected_data_port):
            raise RadarConnectionError("Failed to detect radar ports")
            
        try:
            logger.debug(f"Attempting to open CLI port: {self._detected_cli_port}")
            self.cli_port = serial.Serial(
                self._detected_cli_port,
                baudrate=115200,
                timeout=0.05,
                exclusive=True
            )
            logger.debug("CLI port opened successfully")
            
            baudrate = self.data_port_baudrate
            logger.debug(f"Attempting to create reader for data port: {self._detected_data_port}")
            logger.debug(f"Using baudrate: {baudrate}")

            self.data_port = serial.Serial(
                self._detected_data_port,
                baudrate=baudrate,
                timeout=1,
                exclusive=True
            )
            logger.debug("Data port opened successfully")

        except serial.SerialException as e:
            logger.error(f"Failed to open serial port: {str(e)}")
            if self.cli_port and self.cli_port.is_open:
                self.cli_port.close()
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}")
            if self.cli_port and self.cli_port.is_open:
                self.cli_port.close()
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")

    def _parse_header(self, data: np.ndarray) -> None:
        """Parse the radar data packet header."""
        header = {
            'version': int.from_bytes(data[0:4], byteorder='little'),
            'total_packet_len': int.from_bytes(data[4:8], byteorder='little'),
            'platform': int.from_bytes(data[8:12], byteorder='little'),
            'frame_number': int.from_bytes(data[12:16], byteorder='little'),
            'time_cpu_cycles': int.from_bytes(data[16:20], byteorder='little'),
            'num_detected_obj': int.from_bytes(data[20:24], byteorder='little'),
            'num_tlvs': int.from_bytes(data[24:28], byteorder='little'),
            'subframe_number': int.from_bytes(data[28:32], byteorder='little') if  int.from_bytes(data[20:24], byteorder='little') > 0 else None
        }
        return header

    def restart_radar(self) -> bool:
        """Restart the radar sensor to recover from communication issues."""
        try:
            logger.info("Attempting to restart radar due to communication timeout...")
            
            # Stop the sensor
            self.send_command('sensorStop')
            self.is_running = False
            time.sleep(0.1)  # Brief pause
            
            # Clear the buffer
            if hasattr(self, '_buffer'):
                self._buffer = b''
            
            # Simply restart the sensor without reconfiguration
            self.send_command('sensorStart')
            self.is_running = True
            
            logger.info("Radar restarted successfully (fast restart)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart radar: {e}")
            return False

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """Read one frame using a single read_until per call and a rolling buffer.

        Approach:
        - Call read_until(MAGIC) once per invocation; append to an internal buffer
        - Find the last two MAGIC markers and parse the frame between them
        - If only one MAGIC is present, return None and wait for next call
        """
        if not self.is_running:
            logger.error("Radar is not running. Please start the radar first.")
            return None

        try:
            # Ensure rolling buffer exists
            if not hasattr(self, '_buffer'):
                self._buffer = b''

            # Single read_until per call; append whatever arrived
            try:
                chunk = self.data_port.read_until(self.MAGIC_WORD)
            except serial.SerialTimeoutException:
                return None
            if chunk:
                self._buffer += chunk
                # Trim buffer to cap growth
                if len(self._buffer) > self.MAX_BUFFER_SIZE:
                    self._buffer = self._buffer[-self.MAX_BUFFER_SIZE:]

            # Find last two MAGIC positions
            last = self._buffer.rfind(self.MAGIC_WORD)
            if last == -1:
                return None
            prev = self._buffer.rfind(self.MAGIC_WORD, 0, last)
            if prev == -1:
                # Keep only from last magic to minimize buffer
                if last > 0:
                    self._buffer = self._buffer[last:]
                return None

            # We have two markers: parse frame between them
            frame_data = self._buffer[prev + self.MAGIC_WORD_LENGTH:last]
            if len(frame_data) < 32:
                return None
            header = self._parse_header(frame_data[:32])
            total_packet_len = header['total_packet_len']
            # Between magics should contain (total - MAGIC) bytes
            payload_len = total_packet_len - self.MAGIC_WORD_LENGTH - 32
            if payload_len < 0 or len(frame_data) < 32 + payload_len:
                return None

            payload_bytes = frame_data[32:32 + payload_len]
            # Advance buffer to start at last magic for next call
            self._buffer = self._buffer[last:]
            self.total_frames += 1
            self.frames_received += 1
            
            # Check if we've reached the configured number of frames
            if self.should_stop_for_frame_count():
                logger.info(f"Received the configured number of frames ({self.num_frames}), stopping measurement")
                self.stop()
                return None
            
            return header, np.frombuffer(payload_bytes, dtype=np.uint8)

        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def configure_and_start(self) -> None:
        """Configure the radar and start streaming data."""
        if not self.is_connected(): 
            raise RadarConnectionError("Radar not connected")
            
        self.send_profile(ignore_response=False)
        self.reset_frame_count()  # Reset frame counter when starting
        self.send_command('sensorStart')
        self.is_running = True
        logger.info("Radar configured and started")

    def stop(self) -> None:
        """Stop the radar."""
        self.send_command('sensorStop')
        self.is_running = False

    def close(self) -> None:
        """Safely close the radar connection."""
        if self.cli_port and self.cli_port.is_open:
            self.stop()
            self.cli_port.close()
            
        if self.data_port and self.data_port.is_open:
            self.data_port.close()
            
        if self.total_frames > 0:
            total_attempted = self.total_frames + self.failed_reads
            logger.info("Statistics:")
            logger.info(f"Total successful frames: {self.total_frames}")
            logger.info(f"Failed reads: {self.failed_reads}")
            logger.info(f"Missed frames: {self.missed_frames}")
            logger.info(f"Invalid packets: {self.invalid_packets}")
            if total_attempted > 0:
                logger.info(f"Success rate: {100.0*self.total_frames/total_attempted:.1f}%")
            if self.total_frames + self.missed_frames > 0:
                logger.info(f"Frame loss: {100*self.missed_frames/(self.total_frames+self.missed_frames):.1f}%")

    def is_connected(self) -> bool:
        """Check if radar is connected."""
        return (self.cli_port is not None and self.cli_port.is_open and 
                self.data_port is not None and self.data_port.is_open)

    @property
    def data_port_baudrate(self) -> int:
        """Get the configured data port baudrate."""
        if self._detected_cli_port and self._detected_cli_port.startswith('/dev/tty.'):
            return 460800  # Mac can't handle higher baudrate
        else:
            return 460800  # Linux/Windows 


class _BridgeCliAdapter:
    """Minimal serial-like adapter for the radar bridge control channel."""

    def __init__(self, socket: "zmq.Socket"):
        self._socket = socket
        self._lines: deque[bytes] = deque()
        self._open = True

    def write(self, data: bytes) -> None:
        if not self._open:
            raise RadarConnectionError("CLI control channel is closed")

        payload = data or b""
        if not payload.endswith(b"\n"):
            payload += b"\n"

        try:
            self._socket.send(payload, flags=0)
            reply = self._socket.recv(flags=0)
        except zmq.Again as exc:
            raise RadarConnectionError("Timeout communicating with radar bridge control channel") from exc
        except zmq.ZMQError as exc:  # pragma: no cover - depends on runtime environment
            raise RadarConnectionError("Failed to communicate with radar bridge control channel") from exc

        normalized = reply.replace(b"\r\n", b"\n")
        if normalized and not normalized.endswith(b"\n"):
            normalized += b"\n"

        self._lines.clear()
        if normalized:
            for line in normalized.split(b"\n"):
                if not line:
                    continue
                self._lines.append(line + b"\n")

    def readline(self) -> bytes:
        if not self._lines:
            return b""
        return self._lines.popleft()

    @property
    def in_waiting(self) -> int:
        return sum(len(line) for line in self._lines)

    def flushInput(self) -> None:
        self._lines.clear()

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open


class _BridgeDataAdapter:
    """Wrapper providing a serial-like interface for the data channel."""

    def __init__(self, socket: "zmq.Socket"):
        self._socket = socket
        self._open = True

    def recv(self) -> Optional[bytes]:
        if not self._open:
            return None
        try:
            return self._socket.recv(flags=0)
        except zmq.Again:
            return None
        except zmq.ZMQError as exc:  # pragma: no cover - depends on runtime environment
            raise RadarConnectionError("Failed to receive data from radar bridge") from exc

    def close(self) -> None:
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open


class RadarBridgeConnection(RadarConnection):
    """Radar connection backed by the radar bridge ZeroMQ interface."""

    def __init__(
        self,
        control_endpoint: str = DEFAULT_BRIDGE_CONTROL_ENDPOINT,
        data_endpoint: str = DEFAULT_BRIDGE_DATA_ENDPOINT,
        control_timeout_ms: int = 1_000,
        data_timeout_ms: int = 1_000,
    ) -> None:
        if zmq is None:  # pragma: no cover - handled at runtime when dependency missing
            raise RadarConnectionError(
                "pyzmq is required for network transport. Install the optional dependency to use the radar bridge."
            )

        super().__init__()
        self.transport = 'network'
        self.control_endpoint = control_endpoint
        self.data_endpoint = data_endpoint
        self.control_timeout_ms = control_timeout_ms
        self.data_timeout_ms = data_timeout_ms

        self._context: Optional["zmq.Context"] = None
        self._control_socket: Optional["zmq.Socket"] = None
        self._data_socket: Optional["zmq.Socket"] = None
        self._buffer = b""

    def _connect_device(self, serial_number: Optional[str] = None) -> None:  # noqa: ARG002 - signature compatibility
        try:
            self._context = zmq.Context.instance()

            self._control_socket = self._context.socket(zmq.REQ)
            self._control_socket.setsockopt(zmq.LINGER, 0)
            self._control_socket.setsockopt(zmq.RCVTIMEO, self.control_timeout_ms)
            self._control_socket.setsockopt(zmq.SNDTIMEO, self.control_timeout_ms)
            self._control_socket.connect(self.control_endpoint)
            self.cli_port = _BridgeCliAdapter(self._control_socket)

            self._data_socket = self._context.socket(zmq.PULL)
            self._data_socket.setsockopt(zmq.LINGER, 0)
            self._data_socket.setsockopt(zmq.RCVTIMEO, self.data_timeout_ms)
            self._data_socket.setsockopt(zmq.RCVHWM, 10_000)
            self._data_socket.connect(self.data_endpoint)
            self.data_port = _BridgeDataAdapter(self._data_socket)
        except zmq.ZMQError as exc:
            self._teardown_sockets()
            raise RadarConnectionError(f"Failed to connect to radar bridge: {exc}") from exc

    def _teardown_sockets(self) -> None:
        if self._control_socket is not None:
            try:
                self._control_socket.close(0)
            finally:
                self._control_socket = None
        if self._data_socket is not None:
            try:
                self._data_socket.close(0)
            finally:
                self._data_socket = None
        self._context = None
        self.cli_port = None
        self.data_port = None

    def _drain_latest_frame(self, max_drain: int = 50) -> Optional[Tuple[dict, np.ndarray]]:
        """Drain up to max_drain messages and return the latest valid frame.
        
        This function helps prevent buffer buildup by discarding older frames
        and returning only the most recent valid frame data.
        
        Args:
            max_drain: Maximum number of messages to drain from the socket
            
        Returns:
            Tuple of (header, payload) for the latest valid frame, or None if no valid frame found
        """
        if not self._data_socket:
            return None
            
        latest_frame = None
        drained = 0
        
        # Create a poller for non-blocking checks
        poller = zmq.Poller()
        poller.register(self._data_socket, zmq.POLLIN)
        
        while drained < max_drain:
            events = dict(poller.poll(timeout=0))
            if self._data_socket not in events:
                break
                
            try:
                chunk = self._data_socket.recv(flags=zmq.NOBLOCK)
            except zmq.Again:
                break
                
            if not chunk:
                drained += 1
                continue
                
            # Process this chunk to extract frame data
            frame_data = self._process_chunk_for_frame(chunk)
            if frame_data is not None:
                latest_frame = frame_data
                
            drained += 1
            
        return latest_frame

    def _process_chunk_for_frame(self, chunk: bytes) -> Optional[Tuple[dict, np.ndarray]]:
        """Process a chunk of data to extract frame information.
        
        Args:
            chunk: Raw data chunk from the socket
            
        Returns:
            Tuple of (header, payload) if a valid frame is found, None otherwise
        """
        # Maintain a rolling buffer in case multiple frames arrive in one chunk
        self._buffer += chunk
        if len(self._buffer) > self.MAX_BUFFER_SIZE:
            self._buffer = self._buffer[-self.MAX_BUFFER_SIZE:]

        # Align to the first magic word
        start = self._buffer.find(self.MAGIC_WORD)
        if start == -1:
            # No magic word found, discard stale data
            if len(self._buffer) > self.MAGIC_WORD_LENGTH:
                self._buffer = self._buffer[-self.MAGIC_WORD_LENGTH:]
            return None
        if start > 0:
            self._buffer = self._buffer[start:]
            start = 0

        # Ensure we have enough data for header
        required_header_len = self.MAGIC_WORD_LENGTH + 32
        if len(self._buffer) < required_header_len:
            return None

        header_bytes = self._buffer[self.MAGIC_WORD_LENGTH:self.MAGIC_WORD_LENGTH + 32]
        header = self._parse_header(header_bytes)
        total_packet_len = header.get('total_packet_len', 0)
        if total_packet_len <= 0:
            self.invalid_packets += 1
            # Drop the magic word to avoid livelock
            self._buffer = self._buffer[self.MAGIC_WORD_LENGTH:]
            return None

        if len(self._buffer) < total_packet_len:
            # Wait for more data to arrive
            return None

        frame_bytes = self._buffer[self.MAGIC_WORD_LENGTH:total_packet_len]
        self._buffer = self._buffer[total_packet_len:]

        if len(frame_bytes) < 32:
            self.invalid_packets += 1
            return None

        payload_len = total_packet_len - self.MAGIC_WORD_LENGTH - 32
        if payload_len < 0 or len(frame_bytes) < 32 + payload_len:
            self.invalid_packets += 1
            return None

        payload_bytes = frame_bytes[32:32 + payload_len]
        return header, np.frombuffer(payload_bytes, dtype=np.uint8)

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:  # noqa: D401
        """Read and decode a frame from the radar bridge."""
        if not self.is_running:
            logger.error("Radar is not running. Please start the radar first.")
            return None

        if not self.data_port:
            logger.error("Data channel is not available")
            return None

        try:
            chunk = self.data_port.recv()
        except RadarConnectionError as exc:
            logger.error(str(exc))
            self.failed_reads += 1
            return None

        if not chunk:
            return None

        # Process the chunk to extract frame data
        frame_data = self._process_chunk_for_frame(chunk)
        if frame_data is None:
            return None
            
        header, payload_bytes = frame_data

        self.total_frames += 1
        self.frames_received += 1

        if self.should_stop_for_frame_count():
            logger.info(
                f"Received the configured number of frames ({self.num_frames}), stopping measurement"
            )
            self.stop()
            return None

        return header, payload_bytes

    def close(self) -> None:
        super().close()
        self._teardown_sockets()
        self._buffer = b""


def create_radar(
    transport: str = "auto",
    control_endpoint: str = DEFAULT_BRIDGE_CONTROL_ENDPOINT,
    data_endpoint: str = DEFAULT_BRIDGE_DATA_ENDPOINT,
) -> RadarConnection:
    """Factory function to create a radar instance for the requested transport."""

    normalized = (transport or "auto").lower()
    if normalized not in {"auto", "serial", "network"}:
        raise ValueError(f"Unsupported transport '{transport}'. Expected 'auto', 'serial', or 'network'.")

    if normalized == "serial":
        return RadarConnection()

    if normalized == "network":
        return RadarBridgeConnection(control_endpoint=control_endpoint, data_endpoint=data_endpoint)

    # Auto-detect: prefer a locally attached sensor and fall back to the bridge.
    serial_candidate = RadarConnection()
    try:
        detected = serial_candidate.detect_radar_type()
    except Exception:
        detected = None

    if isinstance(detected, str) and detected:
        logger.info("Using serial transport for radar connection")
        return serial_candidate

    logger.info("No serial radar detected. Falling back to radar bridge network transport")
    return RadarBridgeConnection(control_endpoint=control_endpoint, data_endpoint=data_endpoint)
