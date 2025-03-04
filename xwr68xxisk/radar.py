"""
Base module for TI mmWave radar sensors.

This module provides base classes and specialized implementations for different TI mmWave 
radar sensors. It supports:
- XWR68xx series using USB communication
- AWR2544 using Ethernet communication
"""

import serial
import serial.tools.list_ports
import numpy as np
import time
from typing import Tuple, Optional, List
import logging
import socket
from . import defaultconfig
import os
import fcntl
import struct
import math
import json
from mmwserial import UDPReader, RadarReader

logger = logging.getLogger(__name__)


class RadarConnectionError(Exception):
    """Custom exception for radar connection errors."""
    pass


class RadarConnection:
    """Base class for TI mmWave radar sensors."""
    
    # Silicon Labs CP2105
    CP2105_VENDOR_ID = 0x10C4
    CP2105_PRODUCT_ID = 0xEA70
    
    # TI XDS110
    TI_VENDOR_ID = 0x0451
    TI_PRODUCT_ID = 0xBEF3
    
    def __init__(self):
        """Initialize base RadarConnection instance."""
        self.cli_port: Optional[serial.Serial] = None
        self.configuration = ""
        self.version_info = None
        self.serial_number = None
        self.device_type = None  # 'CP2105' or 'XDS110'
        
    @property
    def DEFAULT_CONFIG_FILE(self) -> str:
        """Default configuration string. Must be implemented by derived classes."""
        raise NotImplementedError("Derived classes must implement DEFAULT_CONFIG_FILE")

    def _load_configuration(self, config: Optional[str], default_config: str) -> List[str]:
        """Load and parse configuration from file or string.
        
        Args:
            config: Configuration string or file path. If None, uses default_config.
            default_config: Default configuration string to use if config is None.
            
        Returns:
            List of configuration lines.
            
        Raises:
            FileNotFoundError: If configuration file path is provided but not found.
        """
        if config is None:
            config = default_config
            
        if '\n' in str(config):  # Configuration text
            config_lines = [line.strip() for line in config.splitlines()]
        else:  # File path
            try:
                with open(config, 'r') as config_file:
                    config_lines = [line.rstrip('\r\n') for line in config_file]
            except FileNotFoundError:
                raise FileNotFoundError(f"Configuration file not found: {config}")
                
        return config_lines

    def find_serial_ports(self, serial_number: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Find the radar ports for either Silicon Labs CP2105 or TI XDS110 devices."""
        ports = serial.tools.list_ports.comports()
        cli_port_path = None
        data_port_path = None
        
        for port in ports:
            # Check for CP2105
            if port.vid == self.CP2105_VENDOR_ID and port.pid == self.CP2105_PRODUCT_ID:
                logger.debug(f"Found CP2105 port: {port.description}")
                if "Enhanced" in port.description:
                    cli_port_path = port.device
                elif "Standard" in port.description:
                    data_port_path = port.device
                    self.serial_number = port.serial_number
                    self.device_type = 'CP2105'
                    if serial_number and serial_number != self.serial_number:
                        data_port_path = None
                        cli_port_path = None
                        
            # Check for XDS110
            elif port.vid == self.TI_VENDOR_ID and port.pid == self.TI_PRODUCT_ID:
                logger.debug(f"Found XDS110 port: {port.description}")
                if "ACM0" in port.device:  # CLI port
                    cli_port_path = port.device
                elif "ACM1" in port.device:  # Data port
                    data_port_path = port.device
                    self.serial_number = port.serial_number
                    self.device_type = 'XDS110'
                    if serial_number and serial_number != self.serial_number:
                        data_port_path = None
                        cli_port_path = None
        
        return cli_port_path, data_port_path

    def _read_cli_response(self):
        """Read and return the complete response from the CLI port."""
        response = []
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            # Quick check if data is available
            if not self.cli_port.in_waiting:
                time.sleep(0.001)  # Very short sleep to prevent CPU spinning
                attempt += 1
                continue
                
            # Data is available, read it
            while self.cli_port.in_waiting:
                line = self.cli_port.readline().decode('utf-8').strip()
                if line:  # Only add non-empty lines
                    response.append(line)
                    if line == "mmwDemo:/>" or "Error" in line:  # Command prompt or error indicates end
                        return response
            
            # If we got some response but no prompt yet, keep waiting
            if response:
                attempt = 0  # Reset attempt counter since we're getting data
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
                # Check if this is an actual error or just initialization messages
                has_error = False
                for line in response:
                    if "Error" in line and not (
                        "Debug:" in line or  # Debug messages are not errors
                        "PHY" in line or     # PHY status messages are not errors
                        "Ignored:" in line   # Ignored messages are not errors
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

    def connect(self, config: Optional[str] = None, serial_number: Optional[str] = None) -> None:
        """Connect to the radar sensor.
        
        This base implementation handles the common connection logic.
        Derived classes should override _connect_device() to handle device-specific connection.
        
        Args:
            config: Configuration string or file path. If None, uses default_config_file.
            serial_number: Optional serial number to connect to a specific device.
            
        Raises:
            RadarConnectionError: If connection fails.
        """
        try:
            # Connect to the device (implemented by derived classes)
            self._connect_device(serial_number)
            
            # Load configuration
            self.configuration = self._load_configuration(config, self.DEFAULT_CONFIG_FILE)
            self.version_info = self.get_version()
            
            if not self.version_info:
                raise RadarConnectionError("No response from sensor - check connections")
                
        except (serial.SerialException, socket.error) as e:
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")
            
    def _connect_device(self, serial_number: Optional[str] = None) -> None:
        """Connect to the physical device. Must be implemented by derived classes."""
        raise NotImplementedError("Derived classes must implement _connect_device()")


class XWR68xxRadar(RadarConnection):
    """Class to handle communication with TI XWR68xx radar sensors via USB."""
    
    # Constants
    MAX_BUFFER_SIZE = 2**15
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    MAGIC_WORD_LENGTH = 8
    
    @property
    def DEFAULT_CONFIG_FILE(self) -> str:
        """Default configuration string."""
        return defaultconfig.xwr68xx
    
    def __init__(self):
        """Initialize XWR68xxRadar instance."""
        super().__init__()
        self.data_port: Optional[serial.Serial] = None
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

    def _connect_device(self, serial_number: Optional[str] = None) -> None:
        """Connect to the XWR68xx radar device."""
        # Try to auto-detect ports
        cli_path, data_path = self.find_serial_ports(serial_number)
        
        if cli_path and data_path:
            self.cli_port = serial.Serial(cli_path, 115200, timeout=0.05)
            # Initialize the optimized reader
            self.reader = RadarReader(data_path, debug=True)
            logger.info("Successfully created optimized reader")
        else:
            raise RadarConnectionError("Failed to connect to radar")

    def parse_configuration(self, config_lines: List[str]) -> dict:
        """Parse configuration lines and extract radar parameters.
        
        Args:
            config_lines: List of configuration command lines
            
        Returns:
            Dictionary containing parsed radar parameters
        """
        config_params = {}
        
        for line in config_lines:
            if not line.strip() or line.startswith('%'):
                continue
                
            cfg = line.split()
            if not cfg:
                continue
                
            cmd = cfg[0]
            args = cfg[1::]
            
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
                    
                elif cmd == 'compressionCfg':
                    config_params['compMethod'] = int(args[2])
                    config_params['compRatio'] = float(args[3])
                    config_params['rangeBinsPerBlock'] = int(args[4])
                    
                elif cmd == 'procChainCfg':
                    config_params['procChain'] = int(args[0])
                    config_params['crcType'] = int(args[4])
                    
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing configuration line '{line}': {e}")
                continue
        
        # Calculate derived parameters
        if 'samples' in config_params:
            rangeBins2x = 2 ** (len(bin(config_params['samples'])) - 2)
            if config_params.get('procChain', 0) == 0:
                config_params['rangeBins'] = int(rangeBins2x/2)
            else:
                rangeBins3x = 3 * 2 ** (len(bin(int(config_params['samples']/3))) - 2)
                config_params['rangeBins'] = int(rangeBins3x/2) if rangeBins2x > rangeBins3x else int(rangeBins2x/2)
        
        # Calculate range resolution
        if all(k in config_params for k in ['sampleRate', 'slope', 'rangeBins']):
            config_params['rangeStep'] = (3e8 * config_params['sampleRate'] * 1e3) / (2 * config_params['slope'] * 1e12 * config_params['rangeBins'] * 2)
            config_params['maxRange'] = config_params['rangeStep'] * config_params['rangeBins']
        
        # Calculate compression parameters
        if all(k in config_params for k in ['compMethod', 'rxAnt', 'rangeBinsPerBlock', 'compRatio']):
            if config_params['compMethod'] == 1:
                samplesPerBlock = config_params['rangeBinsPerBlock']
            else:
                samplesPerBlock = config_params['rxAnt'] * config_params['rangeBinsPerBlock']
                
            inputBytesPerBlock = 4 * samplesPerBlock
            outputBytesPerBlock = math.ceil((inputBytesPerBlock * config_params['compRatio']) / 4) * 4
            config_params['achievedDcmpratio'] = outputBytesPerBlock/inputBytesPerBlock
            
            # Calculate packets per chirp and frame
            if 'rangeBins' in config_params:
                numBlocksPerChirp = config_params['rangeBins'] * config_params['rxAnt'] / samplesPerBlock
                maxPayloadSize = 1536 - (16 + 8)  # max - (header+ footer)
                numBlocksPerPayload = int(maxPayloadSize / outputBytesPerBlock)
                config_params['pktsPerChirp'] = math.ceil(numBlocksPerChirp / numBlocksPerPayload)
                config_params['pktsPerFrame'] = config_params['pktsPerChirp'] * config_params['chirpsPerFrame']
                config_params['pktLen'] = int((outputBytesPerBlock * numBlocksPerChirp) / config_params['pktsPerChirp'])
        
        return config_params

    def send_configuration(self, ignore_response: bool = False) -> None:
        """Send the configuration to the radar efficiently."""
        self.cli_port.flushInput()
        
        # Parse configuration and store parameters
        self.radar_params = self.parse_configuration(self.configuration)
        logger.info(f"Parsed radar parameters: {self.radar_params}")
        
        # Save radar parameters to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        params_file = os.path.join(self.debug_dir, f"radar_params_{timestamp}.json")
        with open(params_file, 'w') as f:
            json.dump(self.radar_params, f, indent=4)
        logger.info(f"Saved radar parameters to: {params_file}")
        
        # First, stop the sensor and flush any existing configuration
        init_commands = [
            'sensorStop',
            'flushCfg'
        ]
        
        # Commands must be sent in specific order for proper initialization
        # 1. DFE mode must be set first
        # 2. Then channel config
        # 3. Then ADC config
        # 4. Then remaining configuration
        ordered_commands = {
            'init': init_commands,
            'dfe': [],      # DFE mode commands
            'channel': [],  # Channel configuration
            'adc': [],      # ADC configuration
            'other': []     # All other commands
        }
        
        # Sort commands into their proper groups
        for command in self.configuration:
            if not command.strip() or command.startswith('%'):
                continue  # Skip empty lines and comments
                
            cmd_type = command.split()[0]
            
            if cmd_type == 'dfeDataOutputMode':
                ordered_commands['dfe'].append(command)
            elif cmd_type == 'channelCfg':
                ordered_commands['channel'].append(command)
            elif cmd_type == 'adcCfg':
                ordered_commands['adc'].append(command)
            elif cmd_type not in ['sensorStop', 'flushCfg']:  # Skip if already in init
                ordered_commands['other'].append(command)
        
        # Send all commands in the correct order
        for group in ['init', 'dfe', 'channel', 'adc', 'other']:
            for command in ordered_commands[group]:
                self.cli_port.write(f"{command}\n".encode())
                logger.debug(f"Sent command: {command}")
                if not ignore_response:
                    response = self._read_cli_response()
                    if response:
                        if "Done" not in response:
                            logger.error(f"Error in command '{command}': {response}")
                            raise RadarConnectionError(f"Configuration error: {response}")
                        logger.debug(f"Response: {response}")

    def configure_and_start(self) -> None:
        """Configure the XWR68xx radar and start streaming data."""
        self.send_configuration()
#        if self.reader:
#            self.reader.flush()  # Flush any existing data in the reader
        self.cli_port.write(b'sensorStart\n')
        logger.info("Radar configured and started")

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """
        Read and parse data packets from the radar using the optimized mmwserial reader.
        
        Returns:
            Tuple of (header, payload) arrays if successful, None otherwise
        """
        if not self.reader:
            logger.error("Reader not initialized. Please connect to the radar first.")
            return None
            
        try:
            if packet := self.reader.read_packet():
                self.total_frames += 1
                frame = packet.header.frame_number
                
                # Track frame statistics
                if self.last_frame is not None:
                    if frame != self.last_frame + 1:
                        missed = frame - self.last_frame - 1
                        self.missed_frames += missed
                        logger.warning(f"Missed {missed} frames between {self.last_frame} and {frame}")
                    elif frame <= self.last_frame:
                        logger.error(f"Invalid frame sequence: {self.last_frame} -> {frame}")
                        self.invalid_packets += 1
                
                self.last_frame = frame
                logger.debug(f"Frame {frame}: {packet.header.num_detected_obj} objects, "
                           f"{packet.header.total_packet_len} bytes")
                
                # Convert packet data to numpy arrays
                header = {
                    'version': packet.header.version,
                    'total_packet_len': packet.header.total_packet_len,
                    'platform': packet.header.platform,
                    'frame_number': packet.header.frame_number,
                    'time_cpu_cycles': packet.header.time_cpu_cycles,
                    'num_detected_obj': packet.header.num_detected_obj,
                }
                
                # Convert payload to numpy array
                payload = np.frombuffer(packet.data, dtype=np.uint8)
                
                return header, payload
            else:
                self.failed_reads += 1
                logger.warning("Failed to read packet")
                return None
                
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None


    def close(self) -> None:
        """Safely close the XWR68xx radar connection."""
        if self.cli_port and self.cli_port.is_open:
            self.send_command('sensorStop')
            self.cli_port.close()
#        if self.reader:
#            self.reader.close()
            
        # Log statistics
        if self.total_frames > 0:
            total_attempted = self.total_frames + self.failed_reads
            logger.info(f"\nStatistics:")
            logger.info(f"Total successful frames: {self.total_frames}")
            logger.info(f"Failed reads: {self.failed_reads}")
            logger.info(f"Missed frames: {self.missed_frames}")
            logger.info(f"Invalid packets: {self.invalid_packets}")
            if total_attempted > 0:
                logger.info(f"Success rate: {100.0*self.total_frames/total_attempted:.1f}%")
            if self.total_frames + self.missed_frames > 0:
                logger.info(f"Frame loss: {100*self.missed_frames/(self.total_frames+self.missed_frames):.1f}%")

    def is_connected(self) -> bool:
        """Check if XWR68xx radar is connected."""
        return (self.cli_port is not None and self.cli_port.is_open and 
                self.reader is not None)


class AWR2544Radar(RadarConnection):
    """Class to handle communication with TI AWR2544 radar sensors via Ethernet."""
    
    # Constants
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    DEFAULT_IP = "192.168.33.180"
    DEFAULT_DATA_PORT = 8080
    PACKET_SIZE = 1054
    SOCKET_BUFFER_SIZE = 65536

    @property
    def DEFAULT_CONFIG_FILE(self) -> str:
        """Default configuration string."""
        return defaultconfig.awr2544
    
    def __init__(self, ip_address: str = DEFAULT_IP):
        """Initialize AWR2544Radar instance."""
        super().__init__()
        self.ip_address = ip_address
        self.data_socket: Optional[socket.socket] = None
        self.sequence_number = 0
        self.frame_number = 0
        
        # Buffer for accumulating packets
        self.packet_buffer = []
        self.current_frame = -1
        self.expected_packets = None  # Will be set based on config
        
        # Create debug directory if it doesn't exist
        self.debug_dir = "debug_data"
        os.makedirs(self.debug_dir, exist_ok=True)
        self.frame_count = 0
        
        # Radar parameters
        self.radar_params = {}

    def _connect_device(self, serial_number: Optional[str] = None) -> None:
        """Connect to the AWR2544 radar device.
        
        Args:
            serial_number: Optional serial number to connect to a specific device.
            
        Raises:
            RadarConnectionError: If connection fails.
        """
        # Try to auto-detect CLI port
        cli_path, _ = self.find_serial_ports(serial_number)
        if not cli_path:
            raise RadarConnectionError("Failed to find CLI port")
        
        # Connect CLI port
        self.cli_port = serial.Serial(cli_path, 115200, timeout=0.05)
        
        # Create UDP Data socket
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.SOCKET_BUFFER_SIZE)
        # Allow reuse of the address/port
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.settimeout(5)
        # Bind to the specific port that the radar is sending to
        try:
            self.data_socket.bind(('0.0.0.0', self.DEFAULT_DATA_PORT))
            logger.info(f"UDP socket bound to port {self.DEFAULT_DATA_PORT}")
        except socket.error as e:
            logger.error(f"Failed to bind to port {self.DEFAULT_DATA_PORT}: {e}")
            raise RadarConnectionError(f"Failed to bind UDP socket: {e}")
            
        logger.info(f"Connected to AWR2544 radar at {self.ip_address}")

    def parse_configuration(self, config_lines: List[str]) -> dict:
        """Parse configuration lines and extract radar parameters.
        
        Args:
            config_lines: List of configuration command lines
            
        Returns:
            Dictionary containing parsed radar parameters
        """
        config_params = {}
        
        for line in config_lines:
            if not line.strip() or line.startswith('%'):
                continue
                
            cfg = line.split()
            if not cfg:
                continue
                
            cmd = cfg[0]
            args = cfg[1::]
            
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
                    
                elif cmd == 'compressionCfg':
                    config_params['compMethod'] = int(args[2])
                    config_params['compRatio'] = float(args[3])
                    config_params['rangeBinsPerBlock'] = int(args[4])
                    
                elif cmd == 'procChainCfg':
                    config_params['procChain'] = int(args[0])
                    config_params['crcType'] = int(args[4])
                    
            except (ValueError, IndexError) as e:
                logger.warning(f"Error parsing configuration line '{line}': {e}")
                continue
        
        # Calculate derived parameters
        if 'samples' in config_params:
            rangeBins2x = 2 ** (len(bin(config_params['samples'])) - 2)
            if config_params.get('procChain', 0) == 0:
                config_params['rangeBins'] = int(rangeBins2x/2)
            else:
                rangeBins3x = 3 * 2 ** (len(bin(int(config_params['samples']/3))) - 2)
                config_params['rangeBins'] = int(rangeBins3x/2) if rangeBins2x > rangeBins3x else int(rangeBins2x/2)
        
        # Calculate range resolution
        if all(k in config_params for k in ['sampleRate', 'slope', 'rangeBins']):
            config_params['rangeStep'] = (3e8 * config_params['sampleRate'] * 1e3) / (2 * config_params['slope'] * 1e12 * config_params['rangeBins'] * 2)
            config_params['maxRange'] = config_params['rangeStep'] * config_params['rangeBins']
        
        # Calculate compression parameters
        if all(k in config_params for k in ['compMethod', 'rxAnt', 'rangeBinsPerBlock', 'compRatio']):
            if config_params['compMethod'] == 1:
                samplesPerBlock = config_params['rangeBinsPerBlock']
            else:
                samplesPerBlock = config_params['rxAnt'] * config_params['rangeBinsPerBlock']
                
            inputBytesPerBlock = 4 * samplesPerBlock
            outputBytesPerBlock = math.ceil((inputBytesPerBlock * config_params['compRatio']) / 4) * 4
            config_params['achievedDcmpratio'] = outputBytesPerBlock/inputBytesPerBlock
            
            # Calculate packets per chirp and frame
            if 'rangeBins' in config_params:
                numBlocksPerChirp = config_params['rangeBins'] * config_params['rxAnt'] / samplesPerBlock
                maxPayloadSize = 1536 - (16 + 8)  # max - (header+ footer)
                numBlocksPerPayload = int(maxPayloadSize / outputBytesPerBlock)
                config_params['pktsPerChirp'] = math.ceil(numBlocksPerChirp / numBlocksPerPayload)
                config_params['pktsPerFrame'] = config_params['pktsPerChirp'] * config_params['chirpsPerFrame']
                config_params['pktLen'] = int((outputBytesPerBlock * numBlocksPerChirp) / config_params['pktsPerChirp'])
        
        return config_params

    def send_configuration(self, ignore_response: bool = False) -> None:
        """Send the configuration to the radar efficiently."""
        self.cli_port.flushInput()
        
        # Parse configuration and store parameters
        self.radar_params = self.parse_configuration(self.configuration)
        logger.info(f"Parsed radar parameters: {self.radar_params}")
        
        # Save radar parameters to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        params_file = os.path.join(self.debug_dir, f"radar_params_{timestamp}.json")
        with open(params_file, 'w') as f:
            json.dump(self.radar_params, f, indent=4)
        logger.info(f"Saved radar parameters to: {params_file}")
        
        # First, stop the sensor and flush any existing configuration
        init_commands = [
            'sensorStop',
            'flushCfg'
        ]
        
        # Commands must be sent in specific order for proper initialization
        # 1. DFE mode must be set first
        # 2. Then channel config
        # 3. Then ADC config
        # 4. Then remaining configuration
        ordered_commands = {
            'init': init_commands,
            'dfe': [],      # DFE mode commands
            'channel': [],  # Channel configuration
            'adc': [],      # ADC configuration
            'other': []     # All other commands
        }
        
        # Sort commands into their proper groups
        for command in self.configuration:
            if not command.strip() or command.startswith('%'):
                continue  # Skip empty lines and comments
                
            cmd_type = command.split()[0]
            
            if cmd_type == 'dfeDataOutputMode':
                ordered_commands['dfe'].append(command)
            elif cmd_type == 'channelCfg':
                ordered_commands['channel'].append(command)
            elif cmd_type == 'adcCfg':
                ordered_commands['adc'].append(command)
            elif cmd_type not in ['sensorStop', 'flushCfg']:  # Skip if already in init
                ordered_commands['other'].append(command)
        
        # Send all commands in the correct order
        for group in ['init', 'dfe', 'channel', 'adc', 'other']:
            for command in ordered_commands[group]:
                self.cli_port.write(f"{command}\n".encode())
                logger.debug(f"Sent command: {command}")
                if not ignore_response:
                    response = self._read_cli_response()
                    if response:
                        if "Done" not in response:
                            logger.error(f"Error in command '{command}': {response}")
                            raise RadarConnectionError(f"Configuration error: {response}")
                        logger.debug(f"Response: {response}")

    def configure_and_start(self) -> None:
        """Configure the AWR2544 radar and start streaming data."""
        self.send_configuration()
        
        # Initialize UDP reader if not already done
        if not hasattr(self, 'udp_reader'):
            if 'pktLen' not in self.radar_params:
                logger.error("Radar parameters not properly initialized. Missing pktLen.")
                return
                
            self.udp_reader = UDPReader(
                "0.0.0.0",  # interface
                self.DEFAULT_DATA_PORT,  # port
                self.radar_params['pktLen'],  # frame size
                timeout_ms=1000  # timeout
            )
            logger.info(f"Created UDP reader on port {self.DEFAULT_DATA_PORT}")
        
        # Calculate expected packets based on compression ratio and chirps
        if self.radar_params:
            data_size_per_chirp = self.radar_params.get('rangeBinsPerBlock', 256) * 4  # 4 bytes per sample
            compressed_size = int(data_size_per_chirp * self.radar_params.get('compRatio', 0.5))
            chirps_per_frame = self.radar_params.get('chirpsPerFrame', 128)
            total_data_size = compressed_size * chirps_per_frame
            self.expected_packets = (total_data_size + self.PACKET_SIZE - 1) // self.PACKET_SIZE
            logger.info(f"Expecting {self.expected_packets} packets per frame ({total_data_size} bytes total)")
        
        self.send_command('sensorStart')
        logger.info("Radar configured and started")

    def checkMagicPattern(self, data):
        """Check if data array contains the magic pattern."""
        if len(data) < 4:
            return False
        return data[0:4] == self.MAGIC_WORD[::-1]  # Reverse because of byte order

    def getUint32(self, data):
        """Convert 4 bytes to a 32-bit unsigned integer."""
        return (data[0] +
                data[1]*256 +
                data[2]*65536 +
                data[3]*16777216)

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """
        Read and parse data packets from the radar using mmwserial_rs.
        Looks for magic pattern and extracts frame information from each packet.
        
        Returns:
            Tuple of (header, payload) arrays if successful, None otherwise
        """
        if not self.radar_params:
            logger.error("Radar parameters not initialized. Please configure the radar first.")
            return None
            
        if not hasattr(self, 'udp_reader'):
            logger.error("UDP reader not initialized. Please call configure_and_start first.")
            return None
            
        try:
            # Read frames for one chirp
            frames = self.udp_reader.read_frames(self.radar_params['pktsPerChirp'])
            
            if not frames:
                logger.debug("No frames received")
                return None
                
            # Save frames to file if debug directory exists
            if self.debug_dir:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                for i, frame in enumerate(frames):
                    filename = os.path.join(self.debug_dir, f"radar_data_{timestamp}_chirp_{i}.bin")
                    with open(filename, 'wb') as f:
                        f.write(frame)
                logger.debug(f"Saved {len(frames)} frames to {self.debug_dir}")
            
            # Extract header and payload from first frame
            first_frame = frames[0]
            header = {
                'version': first_frame[0],
                'total_packet_len': first_frame[1],
                'platform': first_frame[2],
                'frame_number': first_frame[3],
                'time_cpu_cycles': first_frame[4],
                'num_detected_obj': first_frame[5],
            }
            payload = np.frombuffer(first_frame[6:], dtype=np.uint8)
            
            # Log frame information
            sequence_number = header['frame_number']
            frame_number = header['frame_number']
            chirp_number = header['frame_number']
            logger.debug(f"Frame {frame_number}, Chirp {chirp_number}, Seq {sequence_number}")
            print(f"Frame {frame_number}, Chirp {chirp_number}, Seq {sequence_number}")
            return None
            return header, payload
            
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

    def read_header(self) -> Optional[dict]:
        """Read a frame header from the AWR2544 sensor."""
        frame_data = self.read_frame()
        if frame_data is None:
            return None
        return frame_data[0]  # Return header portion

    def read_packet(self, num_bytes: int) -> Optional[np.ndarray]:
        """Read frame payload from the AWR2544 sensor."""
        frame_data = self.read_frame()
        if frame_data is None:
            return None
        return frame_data[1]  # Return payload portion

    def close(self) -> None:
        """Safely close the AWR2544 radar connection."""
        if self.cli_port and self.cli_port.is_open:
            self.send_command('sensorStop')
            self.cli_port.close()
        if self.data_socket:
            try:
                self.data_socket.close()
            except:
                pass

    def is_connected(self) -> bool:
        """Check if AWR2544 radar is connected."""
        return (self.cli_port is not None and self.cli_port.is_open and 
                self.data_socket is not None)


def create_radar(radar_type: str, **kwargs) -> RadarConnection:
    """Factory function to create the appropriate radar instance."""
    if radar_type.lower() == "xwr68xx":
        return XWR68xxRadar()
    elif radar_type.lower() == "awr2544":
        return AWR2544Radar(**kwargs)
    else:
        raise ValueError(f"Unknown radar type: {radar_type}")


# Example test function
def test_radar_connection():
    """Test the RadarConnection functionality."""
    # Test XWR68xx
    radar = create_radar("xwr68xx")
    if isinstance(radar, XWR68xxRadar):
        cli_path, data_path = radar.find_serial_ports()
        assert isinstance(cli_path, (str, type(None)))
        assert isinstance(data_path, (str, type(None)))
        if cli_path and data_path:
            assert "COM" in cli_path or "/dev/" in cli_path
            assert "COM" in data_path or "/dev/" in data_path

    # Test AWR2544
    radar = create_radar("awr2544", ip_address="192.168.33.180")
    assert isinstance(radar, AWR2544Radar)
    assert radar.ip_address == "192.168.33.180"

if __name__ == "__main__":
    # Run tests
    test_radar_connection()

