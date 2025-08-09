"""
Base module for TI mmWave radar sensors.

This module provides base class for XWR68xx series radar sensors using USB communication.
"""

import serial
import serial.tools.list_ports
import numpy as np
import time
from typing import Tuple, Optional, List
import logging
import os
import math
import yaml


logger = logging.getLogger(__name__)


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
    
    def __init__(self):
        """Initialize RadarConnection instance."""
        self.cli_port: Optional[serial.Serial] = None
        self.data_port: Optional[serial.Serial] = None
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
        self.debug_dir = "debug_data"
        os.makedirs(self.debug_dir, exist_ok=True)
        self.reader = None
        self.last_frame = None
        self.missed_frames = 0
        self.total_frames = 0
        self.invalid_packets = 0
        self.failed_reads = 0

    @property
    def frame_period(self) -> float:
        """Get the frame period in milliseconds."""
        return self.radar_params['framePeriod']

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
                
                if "usbserial" in device_path:
                    if device_path.endswith("0"):
                        cli_port_path = device_path
                    elif device_path.endswith("1"):
                        data_port_path = device_path
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


    def _read_cli_response(self):
        """Read and return the complete response from the CLI port."""
        response = []
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            if not self.cli_port.in_waiting:
                time.sleep(0.001)
                attempt += 1
                continue
                
            while self.cli_port.in_waiting:
                line = self.cli_port.readline().decode('utf-8').strip()
                if line:
                    response.append(line)
                    if line == "mmwDemo:/>" or "Error" in line:
                        return response
            
            if response:
                attempt = 0
            else:
                attempt += 1
                
        if not response:
            logger.warning("No response from sensor")
        return response

    def send_command(self, command: str, ignore_response: bool = False) -> None:
        """Send a command to the radar and verify responses.
        
        Args:
            command: Command to send to the radar.
            ignore_response: If True, do not wait for a response from the radar.
        """
        self.cli_port.write(f"{command}\n".encode())
        logger.debug(f"Sent command: {command}")
        
        if not ignore_response:
            response = self._read_cli_response()
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

    def get_version(self):
        """Get version information from the sensor."""
        if not self.is_connected():
            logger.error("Radar not connected")
            return None
            
        try:
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
                    config_params['clutterRemoval'] = yaml_config['processing']['clutter_removal']
                    config_params['framePeriod'] = yaml_config['processing']['frame_period_ms']
                    config_params['mobEnabled'] = yaml_config['processing']['mob_enabled']
                    config_params['mobThreshold'] = yaml_config['processing']['mob_threshold']
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
                    chirps_per_frame = (end_chirp - start_chirp + 1) * num_loops
                    config_params['chirpsPerFrame'] = chirps_per_frame
                    if 'framePeriod' not in config_params:
                        config_params['framePeriod'] = float(args[4])
                    # Set num_doppler_bins based on the number of loops
                    config_params['num_doppler_bins'] = num_loops
                    logger.debug(f"FrameCfg: start={start_chirp}, end={end_chirp}, loops={num_loops}, chirpsPerFrame={chirps_per_frame}, num_doppler_bins={config_params['num_doppler_bins']}")
                    
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
                self.frame_period = self.radar_params['framePeriod']
                parts = line.split()
                parts[4] = str(int(self.frame_period))  # Frame period is at index 4
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
                        # Check if response contains "Done" (success)
                        response_text = ' '.join(response)
                        if "Done" not in response_text:
                            # Check if this is an unsupported command error
                            if "is not recognized as a CLI command" in response_text:
                                cmd_name = command.split()[0] if command.split() else "unknown"
                                logger.warning(f"Command '{cmd_name}' is not supported by this firmware version. Skipping command: {command}")
                                logger.debug(f"Response: {response}")
                            else:
                                logger.error(f"Error in command '{command}': {response}")
                                raise RadarConnectionError(f"Configuration error: {response}")
                        else:
                            logger.debug(f"Response: {response}")
        
        baudrate = self.data_port_baudrate
        logger.debug(f"Configuring data port with baudrate: {baudrate}")
        self.cli_port.write(f"configDataPort {baudrate} 0\n".encode())
        if not ignore_response:
            response = self._read_cli_response()
            if response:
                if "Done" not in response:
                    logger.error(f"Error configuring data port: {response}")
                    raise RadarConnectionError(f"Data port configuration error: {response}")
                logger.debug(f"Data port configuration response: {response}")

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
        """Read and parse data packets from the radar."""
        if not self.is_running:
            logger.error("Radar is not running. Please start the radar first.")
            return None
            
        try:
            # Initialize buffer if not exists
            if not hasattr(self, '_buffer'):
                self._buffer = b''
            
            # Keep reading until we have at least two magic words in the buffer
            timeout_start = time.time()
            max_timeout = 3.0  # Maximum timeout of 3 seconds
            
            while True:
                # Check for overall timeout
                if time.time() - timeout_start > max_timeout:
                    logger.warning(f"Timeout waiting for radar data after {max_timeout}s - attempting restart")
                    
                    # Try to restart the radar
                    if self.restart_radar():
                        # Reset timeout and try again
                        timeout_start = time.time()
                        continue
                    else:
                        logger.error("Failed to restart radar, giving up")
                        return None
                
                # Count magic words in current buffer
                magic_count = self._buffer.count(self.MAGIC_WORD)
                logger.debug(f"Magic words in buffer: {magic_count}")
                
                if magic_count >= 2:
                    # We have at least two magic words, can process a frame
                    break
                
                # Try to read more data with shorter timeout
                try:
                    # First check if any data is available
                    if self.data_port.in_waiting == 0:
                        time.sleep(0.001)  # Short sleep to avoid busy waiting
                        continue
                    
                    # Read available data in chunks instead of waiting for magic word
                    chunk_size = min(1024, self.data_port.in_waiting)
                    data = self.data_port.read(chunk_size)
                    
                    if not data:
                        time.sleep(0.001)  # Short sleep before retrying
                        continue
                    
                    # Add the data to our buffer
                    self._buffer += data
                    logger.debug(f"Added {len(data)} bytes to buffer, total: {len(self._buffer)}")
                    
                    # Limit buffer size to prevent memory issues
                    if len(self._buffer) > self.MAX_BUFFER_SIZE:
                        # Keep only the last half of the buffer
                        keep_size = self.MAX_BUFFER_SIZE // 2
                        self._buffer = self._buffer[-keep_size:]
                        logger.warning(f"Buffer size exceeded limit, truncated to {len(self._buffer)} bytes")
                        
                except serial.SerialTimeoutException:
                    # Timeout on individual read, continue the loop
                    continue
                except Exception as e:
                    logger.error(f"Error reading from data port: {e}")
                    return None
            
            # Now we have at least two magic words in the buffer
            # Find the first magic word position
            first_magic_pos = self._buffer.find(self.MAGIC_WORD)
            if first_magic_pos == -1:
                logger.debug(f"No first magic word found in buffer, clearing buffer")
                self._buffer = b''
                return None
            
            # Find the second magic word position
            second_magic_pos = self._buffer.find(self.MAGIC_WORD, first_magic_pos + 1)
            if second_magic_pos == -1:
                logger.debug(f"No second magic word found in buffer")
                # This shouldn't happen since we checked for >= 2 magic words above
                # But if it does, clear the buffer to recover
                self._buffer = b''
                return None
            
            # Extract frame data between the two magic words
            frame_data = self._buffer[first_magic_pos + len(self.MAGIC_WORD):second_magic_pos]
            logger.debug(f"Length of frame data: {len(frame_data)}")
            
            # Check if we have enough data for header
            if len(frame_data) < 32:
                logger.debug(f"Not enough data for header: {len(frame_data)} < 32")
                return None
            
            # Parse header
            header_data = frame_data[:32]
            header = self._parse_header(header_data)
            frame = header['frame_number']           
            self.last_frame = frame
            
            # Calculate payload length
            total_packet_len = header['total_packet_len']
            payload_length = total_packet_len - 32 - self.MAGIC_WORD_LENGTH
            
            if payload_length < 0:
                logger.debug(f"Invalid payload length: {payload_length}")
                # Invalid packet, remove everything up to second magic word and continue
                self._buffer = self._buffer[second_magic_pos:]
                return None
            
            # Check if we actually have enough data for the complete payload
            if len(frame_data) < 32 + payload_length:
                logger.debug(f"Incomplete frame data: have {len(frame_data)}, need {32 + payload_length}")
                # Don't remove from buffer, just return None and try again later
                return None
                                    
            # Extract payload
            payload_data = frame_data[32:32 + payload_length]
            
            # Remove the processed frame from buffer (everything up to second magic word)
            old_buffer_size = len(self._buffer)
            self._buffer = self._buffer[second_magic_pos:]
            new_buffer_size = len(self._buffer)
            
            logger.debug(f"Buffer: {old_buffer_size} -> {new_buffer_size} bytes (removed {second_magic_pos})")
            logger.debug(f"Magic words in buffer after removal: {self._buffer.count(self.MAGIC_WORD)}")
            
            self.total_frames += 1
            payload = np.frombuffer(payload_data, dtype=np.uint8)
            
            return header, payload
                
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def configure_and_start(self) -> None:
        """Configure the radar and start streaming data."""
        if not self.is_connected(): 
            raise RadarConnectionError("Radar not connected")
            
        self.send_profile(ignore_response=False)
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


def create_radar() -> RadarConnection:
    """Factory function to create a radar instance."""
    return RadarConnection()

