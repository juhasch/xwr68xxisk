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
        self.is_running = False
        self._clutter_removal = False  # Default value for clutter removal
        # Store detected ports
        self._detected_cli_port = None
        self._detected_data_port = None

    @property
    def clutterRemoval(self) -> bool:
        """Get the static clutter removal setting.
        
        Returns:
            bool: True if static clutter removal is enabled, False otherwise.
        """
        return self._clutter_removal

    @clutterRemoval.setter
    def clutterRemoval(self, value: bool) -> None:
        """Set the static clutter removal setting.
        
        Args:
            value (bool): True to enable static clutter removal, False to disable.
        """
        self._clutter_removal = value
        self.send_command('clutterRemoval -1 ' + ('1' if value else '0') + '\n')

    def find_serial_ports(self, serial_number: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """Find the radar ports for either Silicon Labs CP2105 or TI XDS110 devices."""
        ports = serial.tools.list_ports.comports()
        cli_port_path = None
        data_port_path = None
        
        for port in ports:
            # Check for CP2105
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
                    self.device_type = 'CP2105'
                elif "Enhanced" in port.description:  # Windows/Linux
                    cli_port_path = device_path
                elif "Standard" in port.description:  # Windows/Linux
                    data_port_path = device_path
                    self.serial_number = port.serial_number
                    self.device_type = 'CP2105'
                    
                if serial_number and serial_number != self.serial_number:
                    data_port_path = None
                    cli_port_path = None
                        
            # Check for XDS110
            elif port.vid == self.TI_VENDOR_ID and port.pid == self.TI_PRODUCT_ID:
                logger.debug(f"Found XDS110 port: {port.description}")
                device_path = port.device
                if device_path.startswith('/dev/cu.'):
                    device_path = device_path.replace('/dev/cu.', '/dev/tty.')
                    
                if "ACM0" in device_path:  # CLI port
                    cli_port_path = device_path
                elif "ACM1" in device_path:  # Data port
                    data_port_path = device_path
                    self.serial_number = port.serial_number
                    self.device_type = 'XDS110'
                    if serial_number and serial_number != self.serial_number:
                        data_port_path = None
                        cli_port_path = None
        
        if cli_port_path and data_port_path:
            logger.info(f"Found CLI port: {cli_port_path}")
            logger.info(f"Found Data port: {data_port_path}")
            logger.info(f"Serial number: {self.serial_number}")
        
        return cli_port_path, data_port_path

    def send_configuration(self, ignore_response: bool = False) -> None:
        """Send the configuration to the radar efficiently."""
        self.cli_port.flushInput()
        
        # Parse configuration and store parameters
        self.radar_params = self.parse_configuration(self.configuration)
        logger.info(f"Parsed radar parameters:{self._format_radar_params(self.radar_params)}")
        
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
        
        # Configure data port baudrate after other configuration
        # Set baudrate based on OS platform
        if self._detected_cli_port.startswith('/dev/tty.'):  # macOS
            baudrate = 460800
        else:  # Windows/Linux
            baudrate = 921600
        
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
        """Connect to the XWR68xx radar device."""
        # Use already detected ports if available, otherwise detect them
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
                exclusive=True  # Ensure exclusive access to the port
            )
            logger.debug("CLI port opened successfully")
            
            # Set baudrate based on OS platform
            if self._detected_cli_port.startswith('/dev/tty.'):  # macOS
                baudrate = 460800
            else:  # Windows/Linux
                baudrate = 921600
                
            # Initialize the optimized reader
            logger.debug(f"Attempting to create reader for data port: {self._detected_data_port}")
            logger.debug(f"Using baudrate: {baudrate}")
            
            # Create the reader with the configured baudrate
            self.reader = RadarReader(self._detected_data_port, baudrate=baudrate, debug=False)
            logger.info("Successfully created optimized reader")
        except serial.SerialException as e:
            logger.error(f"Failed to open serial port: {str(e)}")
            # Clean up if partial connection was established
            if self.cli_port and self.cli_port.is_open:
                self.cli_port.close()
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error during connection: {str(e)}")
            # Clean up if partial connection was established
            if self.cli_port and self.cli_port.is_open:
                self.cli_port.close()
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")

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

    def read_frame(self) -> Optional[Tuple[dict, np.ndarray]]:
        """
        Read and parse data packets from the radar using the optimized mmwserial reader.
        
        Returns:
            Tuple of (header, payload) arrays if successful, None otherwise
        """
        if not self.reader:
            logger.error("Reader not initialized. Please connect to the radar first.")
            return None
        
        if not self.is_running:
            logger.error("Radar is not running. Please start the radar first.")
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

    def configure_and_start(self) -> None:
        """Configure the XWR68xx radar and start streaming data."""
        self.send_configuration()
        self.cli_port.write(b'sensorStart\n')
        self.is_running = True
        logger.info("Radar configured and started")

    def stop(self) -> None:
        """Stop the XWR68xx radar."""
        self.send_command('sensorStop')
        self.is_running = False

    def close(self) -> None:
        """Safely close the XWR68xx radar connection."""
        if self.cli_port and self.cli_port.is_open:
            self.stop()
            self.cli_port.close()
            
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
            return header, payload
            
        except Exception as e:
            logger.error(f"Error reading frame: {e}")
            return None

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