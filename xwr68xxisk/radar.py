"""
USB communication module for TI mmWave radar sensors.

This module provides a RadarConnection class to handle serial communication with TI mmWave 
radar sensors using the Silicon Labs CP2105 dual UART bridge. It provides functionality to:
- Auto-detect the CLI and Data ports
- Configure the radar sensor using a configuration file or text
- Manage serial communication buffers
"""

import serial
import serial.tools.list_ports
import numpy as np
import time
from typing import Tuple, Optional, List
import logging

logger = logging.getLogger(__name__)


class RadarConnectionError(Exception):
    """Custom exception for radar connection errors."""
    pass

class RadarConnection:
    """Class to handle communication with TI mmWave radar sensors."""
    
    # Constants
    MAX_BUFFER_SIZE = 2**15
    MAGIC_WORD = b'\x02\x01\x04\x03\x06\x05\x08\x07'
    MAGIC_WORD_LENGTH = 8
    
    # Silicon Labs CP2105
    CP2105_VENDOR_ID = 0x10C4
    CP2105_PRODUCT_ID = 0xEA70
    
    # TI XDS110
    TI_VENDOR_ID = 0x0451
    TI_PRODUCT_ID = 0xBEF3
    
    def __init__(self):
        """Initialize RadarConnection instance."""
        self.cli_port: Optional[serial.Serial] = None
        self.data_port: Optional[serial.Serial] = None
        self.byte_buffer = np.zeros(self.MAX_BUFFER_SIZE, dtype='uint8')
        self.byte_buffer_length = 0
        self.current_index = 0
        self.have_waited = False
        self.configuration = ""
        self.version_info = None
        self.serial_number = None
        self.device_type = None  # 'CP2105' or 'XDS110'

    def find_serial_ports(self, serial_number: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Find the radar ports for either Silicon Labs CP2105 or TI XDS110 devices.
        
        Args:
            serial_number (Optional[str]): Optional serial number to match specific device
            
        Returns:
            Tuple[Optional[str], Optional[str]]: Tuple of (CLI port path, Data port path) 
            or (None, None) if not found.
        """
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
                        logger.debug(f"Serial number mismatch: {self.serial_number} != {serial_number}")
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
                        logger.debug(f"Serial number mismatch: {self.serial_number} != {serial_number}")
                        data_port_path = None
                        cli_port_path = None
        
        if cli_port_path and data_port_path:
            logger.info(f"Found CLI port: {cli_port_path}")
            logger.info(f"Found Data port: {data_port_path}")
            logger.info(f"Device type: {self.device_type}")
            logger.info(f"Serial number: {self.serial_number}")
            return cli_port_path, data_port_path
        
        logger.warning("No compatible radar ports found")
        return None, None

    def connect(self, config: str, serial_number: Optional[str] = None) -> None:
        """
        Connect to the radar and store the configuration.
        
        Args:
            config (str): Either path to the configuration file or configuration text
            serial_number (Optional[str]): Optional serial number to match specific device
            
        Raises:
            RadarConnectionError: If connection to the radar fails
            FileNotFoundError: If configuration file is not found
        """
        baudrate = 115200*9  # Highest working baudrate for the sensor
        try:
            # Try to auto-detect ports
            cli_path, data_path = self.find_serial_ports(serial_number)
            
            if cli_path and data_path:
                self.cli_port = serial.Serial(cli_path, 115200, timeout=0.05)
                self.data_port = serial.Serial(data_path, baudrate, timeout=0.2)
            else:
                raise RadarConnectionError("Failed to connect to radar")

            # Check if config is a file path or configuration text
            if '\n' in config:  # Configuration text
                config_lines = [line.strip() for line in config.splitlines()]
            else:  # File path
                try:
                    with open(config, 'r') as config_file:
                        config_lines = [line.rstrip('\r\n') for line in config_file]
                except FileNotFoundError:
                    raise FileNotFoundError(f"Configuration file not found: {config}")
                
            self.configuration = config_lines

            # Test communication by sending a simple command and store version info
            self.version_info = self.get_version()
            if not self.version_info:
                raise RadarConnectionError("No response from sensor - check connections and power")

            # set data port to given baudrate
            #self.send_command(f"configDataPort {baudrate} 1")
            #data = self.data_port.read(16)
            #if len(data) == 16 and data == b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff':
            #    logger.info(f"Data port set to given baudrate {baudrate}")
        
        except serial.SerialException as e:
            raise RadarConnectionError(f"Failed to connect to radar: {str(e)}")

    def send_configuration(self, ignore_response: bool = False) -> None:
        """
        Send the configuration to the radar and verify responses.
        
        Raises:
            RadarConnectionError: If an error response is received from the radar
        """
        self.cli_port.flushInput()
        for command in self.configuration:
            if not command.strip() or command.startswith('%'):
                continue  # Skip empty lines and comments
            self.send_command(command, ignore_response=ignore_response)

    def send_command(self, command: str, ignore_response: bool = False) -> None:
        """Send a command to the radar and verify responses.
        
        Args:
            command (str): The command to send to the radar
            ignore_response (bool, optional): If True, do not check the response

        Raises:
            RadarConnectionError: If an error response is received from the radar
        """
        self.cli_port.write(f"{command}\n".encode())
        logger.debug(f"Sent command: {command}")
        
        # Read and check response
        time.sleep(0.05)
        response = self._read_cli_response()
        if response and not ignore_response:
            # Check if "Done" appears in the response
            if "Done" not in response:
                logger.error(f"Error in command '{command}': {response}")
                raise RadarConnectionError(f"Configuration error: {response}")
            logger.debug(f"Response: {response}")
            

    def configure_and_start(self) -> None:
        """Configure the radar and start streaming data."""
        self.send_configuration()
        self.data_port.flushInput()
        self.cli_port.write(b'sensorStart\n')
        logger.info("Radar configured and started")

    def read_header(self) -> Optional[np.ndarray]:
        """
        Read a packet from the sensor by looking for the magic word signature.
        
        Args:
            num_bytes (int, optional): Ignored parameter kept for backwards compatibility
            
        Returns:
            Optional[np.ndarray]: Array of read bytes or None if read fails
        """
        counter = 0
        while True:            
            chunk = self.data_port.read(8)
            #print(f"Chunk: {chunk}")
            if chunk == self.MAGIC_WORD:
                counter = 0
                #print("Magic word found")
                header = self.data_port.read(32)
                if len(header) < 32:
                    logger.warning("Incomplete header read")
                    continue
                #print(f"Header: {header}")
                time.sleep(0.08)
                return header
            else:
                counter += 1
                if counter > 10000:
                    logger.warning("No magic word found")
                    return None
                time.sleep(0.001)  # Short sleep if no data available  


    def read_packet(self, num_bytes: int) -> Optional[np.ndarray]:
        """Read a complete packet from the sensor."""
        #print(f"Reading packet of length {num_bytes}, have read {self.data_port.in_waiting} bytes")
        num_bytes = self.data_port.in_waiting
        packet = self.data_port.read(num_bytes)
        return packet

    def close(self) -> None:
        """Safely close the serial ports."""
        if self.cli_port and self.cli_port.is_open:
            self.cli_port.write('sensorStop\n'.encode())
            self.cli_port.close()
        if self.data_port and self.data_port.is_open:
            self.data_port.close()

    def is_connected(self) -> bool:
        """
        Check if both CLI and Data ports are connected and open.
        
        Returns:
            bool: True if both ports are connected and open
        """
        return (self.cli_port is not None and self.cli_port.is_open and 
                self.data_port is not None and self.data_port.is_open)

    def get_version(self):
        """Get version information from the sensor."""
        if not self.is_connected():
            return "Error: Sensor not connected"
            
        try:
            # Send version command
            self.cli_port.flushInput()
            self.cli_port.write(b'version\n')
            time.sleep(0.05)
            response = self._read_cli_response()
            # Remove the first and last two lines from the response
            if response and len(response) >= 2:
                return response[1:-2]
            return response
        except Exception as e:
            return [f"Error getting version: {e}"]

    def send_config(self, config_text):
        """Send configuration to the sensor."""
        if not self.is_connected():
            raise RadarConnectionError("Sensor not connected")
            
        try:
            print("Sending configuration to sensor...")
            self.cli_port.write(b'sensorStop\n')
            self._read_cli_response()  # Clear stop response
            
            # Send each line of the configuration
            responses = []
            for line in config_text.splitlines():
                if line.strip() and not line.startswith('#'):
                    self.cli_port.write(f"{line}\n".encode())
                    response = self._read_cli_response()
                    if response:
                        responses.extend(response)
            
            return responses
            
        except Exception as e:
            raise RadarConnectionError(f"Error sending configuration: {e}")

    def _read_cli_response(self):
        """Read and return the complete response from the CLI port."""
        response = []
        
        while self.cli_port.in_waiting:
            line = self.cli_port.readline().decode('utf-8').strip()
            if line:  # Only add non-empty lines
                response.append(line)
        
        if not response:
            logger.warning("No response from sensor")
        return response

# Example test function
def test_radar_connection():
    """Test the RadarConnection functionality."""
    radar = RadarConnection()
    cli_path, data_path = radar.find_serial_ports()
    assert isinstance(cli_path, (str, type(None)))
    assert isinstance(data_path, (str, type(None)))
    if cli_path and data_path:
        assert "COM" in cli_path or "/dev/" in cli_path
        assert "COM" in data_path or "/dev/" in data_path

if __name__ == "__main__":
    # Run tests
    test_radar_connection()

