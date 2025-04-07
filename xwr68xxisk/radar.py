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


logger = logging.getLogger(__name__)


class RadarConnectionError(Exception):
    """Custom exception for radar connection errors."""
    pass


class RadarConnection:
    """Base class for TI XWR68xx radar sensors."""
    
    # Silicon Labs CP2105
    CP2105_VENDOR_ID = 0x10C4
    CP2105_PRODUCT_ID = 0xEA70
    
    # Constants
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
        self.device_type = 'CP2105'  # Only CP2105 is supported
        self.is_running = False
        self._clutter_removal = False  # Default value for clutter removal
        self.frame_period = 200  # Default frame period in milliseconds
        self.mob_enabled = False  # Default value for moving object detection
        self.mob_threshold = 0.5  # Default value for moving object detection threshold
        
        # Store detected ports
        self._detected_cli_port = None
        self._detected_data_port = None
        
        # Buffer and statistics
        self.byte_buffer = np.zeros(self.MAX_BUFFER_SIZE, dtype='uint8')
        self.byte_buffer_length = 0
        self.current_index = 0
        self.radar_params = {}
        self.debug_dir = "debug_data"
        os.makedirs(self.debug_dir, exist_ok=True)
        self.reader = None
        self.last_frame = None
        self.missed_frames = 0
        self.total_frames = 0
        self.invalid_packets = 0
        self.failed_reads = 0

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
                
                # Convert cu. to tty. on macOS for more reliable access
                if device_path.startswith('/dev/cu.'):
                    device_path = device_path.replace('/dev/cu.', '/dev/tty.')
                
                # Handle different naming conventions based on OS
                if "SLAB_USBtoUART" in device_path:  # macOS
                    if "UART3" in device_path:  # CLI port on macOS
                        cli_port_path = device_path
                    else:  # Data port on macOS
                        data_port_path = device_path
                    self.serial_number = port.serial_number
                elif "Enhanced" in port.description:  # Windows/Linux
                    cli_port_path = device_path
                elif "Standard" in port.description:  # Windows/Linux
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
        """Send a command to the radar and verify responses."""
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
            return "Error: Sensor not connected"
            
        try:
            self.cli_port.flushInput()
            self.cli_port.write(b'version\n')
            time.sleep(0.05)
            response = self._read_cli_response()
            if response and len(response) >= 2:
                return response[1:-2]
            return response
        except Exception as e:
            return [f"Error getting version: {e}"]

    def connect(self, config: str, serial_number: Optional[str] = None) -> None:
        """Connect to the radar sensor.
        
        Args:
            config: Configuration string or path to a configuration file.
            serial_number: Optional[str] = None - Serial number of the radar to connect to.
        """
        try:
            self._connect_device(serial_number)
            
            # If config is a file path, read it
            if config and os.path.isfile(config):
                logger.info(f"Reading configuration from file: {config}")
                with open(config, 'r') as f:
                    self.profile = f.read()
            else:
                logger.info("Using supplied configuration")
                self.profile = config
            self.version_info = self.get_version()
            
            if not self.version_info:
                raise RadarConnectionError("No response from sensor - check connections")
                
        except serial.SerialException as e:
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")
            
        except Exception as e:
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")

    def set_frame_period(self, period_ms: float) -> None:
        """Set the frame period in milliseconds."""
        if not self.is_connected():
            logger.error("Radar not connected")
            return
            
        try:
            self.send_command(f'frameCfg 0 1 16 0 {int(period_ms)} 1 0')
            self.frame_period = period_ms
            logger.info(f"Frame period set to {period_ms}ms")
        except Exception as e:
            logger.error(f"Error setting frame period: {e}")

    def parse_configuration(self, config_lines: List[str]) -> dict:
        """Parse configuration lines and extract radar parameters."""
        config_params = {}
        
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
                    config_params['samples'] = int(args[-5])
                    config_params['sampleRate'] = int(args[-4])
                    config_params['slope'] = float(args[7])
                    
                elif cmd == 'frameCfg':
                    config_params['chirpsPerFrame'] = (int(args[1]) - int(args[0]) + 1) * int(args[2])
                    config_params['framePeriod'] = float(args[4])
                    self.frame_period = float(args[4])
                    
                elif cmd == 'multiObjBeamForming':
                    if len(args) >= 3:
                        self.mob_enabled = int(args[1]) == 1
                        self.mob_threshold = float(args[2])
                        config_params['mobEnabled'] = self.mob_enabled
                        config_params['mobThreshold'] = self.mob_threshold
                        
                elif cmd == 'clutterRemoval':
                    if len(args) >= 2:
                        self._clutter_removal = int(args[1]) == 1
                        config_params['clutterRemoval'] = self._clutter_removal
                    
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing configuration line '{line}': {e}")
                continue
        
        # Calculate derived parameters
        if 'samples' in config_params:
            rangeBins2x = 2 ** (len(bin(config_params['samples'])) - 2)
            config_params['rangeBins'] = int(rangeBins2x/2)
        
        # Calculate range resolution
        if all(k in config_params for k in ['sampleRate', 'slope', 'rangeBins']):
            config_params['rangeStep'] = (3e8 * config_params['sampleRate'] * 1e3) / (2 * config_params['slope'] * 1e12 * config_params['rangeBins'] * 2)
            config_params['maxRange'] = config_params['rangeStep'] * config_params['rangeBins']
        
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
            
        config_lines = [line.strip() for line in self.profile.split('\n') if line.strip()]
        self.radar_params = self.parse_configuration(config_lines)
        logger.info(f"Parsed radar parameters:{self._format_radar_params(self.radar_params)}")
        
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
        
        for line in config_lines:
            if not line or line.startswith('%') or line.startswith('sensorStart'):
                continue
                
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
                        if "Done" not in response:
                            logger.error(f"Error in command '{command}': {response}")
                            raise RadarConnectionError(f"Configuration error: {response}")
                        logger.debug(f"Response: {response}")
        
        if self._detected_cli_port.startswith('/dev/tty.'):  # macOS
            self.baudrate = 460800
        else:  # Windows/Linux
            self.baudrate = 921600
        
        logger.debug(f"Configuring data port with baudrate: {self.baudrate}")
        self.cli_port.write(f"configDataPort {self.baudrate} 0\n".encode())
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
            
            if self._detected_cli_port.startswith('/dev/tty.'):  # macOS
                baudrate = 460800
            else:  # Windows/Linux
                baudrate = 921600
                
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

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """Read and parse data packets from the radar."""
        if not self.is_running:
            logger.error("Radar is not running. Please start the radar first.")
            return None
            
        try:
            if packet := self.data_port.read_until(self.MAGIC_WORD):
                self.total_frames += 1
                header = self._parse_header(packet)
                frame = header['frame_number']
                
                if self.last_frame is not None:
                    if frame != self.last_frame + 1:
                        missed = frame - self.last_frame - 1
                        self.missed_frames += missed
                        logger.warning(f"Missed {missed} frames between {self.last_frame} and {frame}")
                    elif frame <= self.last_frame:
                        logger.error(f"Invalid frame sequence: {self.last_frame} -> {frame}")
                        self.invalid_packets += 1
                
                self.last_frame = frame
                logger.debug(f"Frame {frame}: {header['num_detected_obj']} objects, "
                           f"{header['total_packet_len']} bytes")
                
                payload = np.frombuffer(packet[32:], dtype=np.uint8)
                
                return header, payload
            else:
                self.failed_reads += 1
                logger.warning("Failed to read packet")
                return None
                
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def configure_and_start(self) -> None:
        """Configure the radar and start streaming data."""
        self.send_profile()
        self.cli_port.write(b'sensorStart\n')
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


def create_radar() -> RadarConnection:
    """Factory function to create a radar instance."""
    return RadarConnection()

