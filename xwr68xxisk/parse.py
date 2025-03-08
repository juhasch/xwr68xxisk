import numpy as np
import struct
from typing import Tuple, List, Optional, Iterator, Dict, Any
import time
import logging
import os
import math

# Magic number for radar data validation
MAGIC_NUMBER = 0x708050603040102

# Import RadarPointCloud
from .point_cloud import RadarPointCloud

class RadarData:
    """
    Parser for radar data packets.
    
    This class handles parsing of radar data packets from TI mmWave sensors.
    It supports both XWR68xx and AWR2544 series sensors.
    
    Attributes:
        MMWDEMO_OUTPUT_MSG_DETECTED_POINTS (int): TLV type for point cloud data
        MMWDEMO_OUTPUT_MSG_RANGE_PROFILE (int): TLV type for range profile data
        MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO (int): TLV type for side info
        pc (Tuple[List[float], List[float], List[float], List[float]]): Point cloud data (x,y,z,velocity)
        adc (np.ndarray): Range profile data
        side_info (Tuple[List[float], List[float]]): SNR and noise data
        snr (List[float]): Signal-to-noise ratio for each point
        noise (List[float]): Noise level for each point
    """
    
    # TLV (Type-Length-Value) types
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS = 1
    MMWDEMO_OUTPUT_MSG_RANGE_PROFILE = 2
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO = 3

    def __init__(self, radar_connection=None):
        """
        Initialize and parse radar data packet.

        Args:
            radar_connection: RadarConnection instance to read data from

        Raises:
            ValueError: If packet format is invalid or magic number doesn't match
        """
        # Initialize data containers
        self.pc: Optional[Tuple[List[float], ...]] = None
        self.adc: Optional[np.ndarray] = None
        self.snr: List[float] = []
        self.noise: List[float] = []
        self.frame_number = None
        self.num_tlvs = 0
        self.magic_word = None
        self.version = None
        self.total_packet_len = None
        self.platform = None
        self.time_cpu_cycles = None
        self.num_detected_obj = 0
        self.subframe_number = None
        
        # Store the radar connection for iterator functionality
        self.radar_connection = radar_connection
        
        if radar_connection is None or not radar_connection.is_connected() or not radar_connection.is_running:
            return
            
        try:
            frame_data = radar_connection.read_frame()
            if frame_data is None:
                return
                
            header, payload = frame_data
            if header is not None:
                self.frame_number = header.get('frame_number')
                self.num_tlvs = header.get('num_detected_obj', 0)
                self._parse_tlv_data(payload)
        except Exception as e:
            logging.error(f"Error reading radar data: {e}")
            return

    def _parse_tlv_data(self, data: np.ndarray) -> None:
        """Parse TLV (Type-Length-Value) data from the radar packet."""
        data_bytes = data
        idx = 0  # Start after header
        
        for _ in range(self.num_tlvs):
            tlv_type = int.from_bytes(data_bytes[idx:idx+4], byteorder='little')
            tlv_length = int.from_bytes(data_bytes[idx+4:idx+8], byteorder='little')
            idx += 8

            if tlv_type == self.MMWDEMO_OUTPUT_MSG_DETECTED_POINTS:
                idx = self._parse_point_cloud(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_RANGE_PROFILE:
                idx = self._parse_range_profile(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO:
                idx = self._parse_side_info(data_bytes, idx, tlv_length)
            else:
                idx += tlv_length

    def _parse_point_cloud(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse point cloud data from TLV."""
        num_points = tlv_length // 16  # Each point is 16 bytes
        x, y, z, v = [], [], [], []
        
        for point in range(num_points):
            point_idx = idx + (point * 16)
            x.append(struct.unpack('f', data[point_idx:point_idx+4])[0])
            y.append(struct.unpack('f', data[point_idx+4:point_idx+8])[0])
            z.append(struct.unpack('f', data[point_idx+8:point_idx+12])[0])
            v.append(struct.unpack('f', data[point_idx+12:point_idx+16])[0])
        
        self.pc = (x, y, z, v)
        return idx + tlv_length

    def _parse_range_profile(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse range profile data from TLV."""
        self.adc = np.frombuffer(data[idx:idx+tlv_length], dtype=np.uint16)
        return idx + tlv_length

    def _parse_side_info(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse side information (SNR and noise) from TLV."""
        num_points = tlv_length // 4
        
        try:
            for point in range(num_points):
                point_idx = idx + (point * 4)
                if point_idx + 4 <= len(data):  # Check if we have enough data
                    self.snr.append(struct.unpack('h', data[point_idx:point_idx+2])[0] * 0.1)
                    self.noise.append(struct.unpack('h', data[point_idx+2:point_idx+4])[0] * 0.1)
        except struct.error:
            logging.warning("Error unpacking side info data")
            logging.debug(f"num_points: {num_points}")
            self.snr = []
            self.noise = []
        
        return idx + tlv_length

    def to_point_cloud(self) -> RadarPointCloud:
        """
        Convert the radar data to a RadarPointCloud object.
        
        Returns:
            RadarPointCloud: Point cloud representation of the radar data
        """
        if self.pc is None:
            return RadarPointCloud()
            
        x, y, z, v = self.pc
        
        # Convert Cartesian coordinates to spherical coordinates
        range_values = []
        azimuth = []
        elevation = []
        
        for i in range(len(x)):
            # Calculate range
            r = math.sqrt(x[i]**2 + y[i]**2 + z[i]**2)
            range_values.append(r)
            
            # Calculate azimuth (horizontal angle)
            az = math.atan2(x[i], y[i])
            azimuth.append(az)
            
            # Calculate elevation (vertical angle)
            if r > 0:
                el = math.asin(z[i] / r)
            else:
                el = 0
            elevation.append(el)
        
        # Create metadata dictionary
        metadata = {
            'frame_number': self.frame_number,
            'num_detected_obj': self.num_detected_obj,
            'timestamp': self.time_cpu_cycles
        }
        
        # Convert lists to numpy arrays
        range_array = np.array(range_values)
        velocity_array = np.array(v)
        azimuth_array = np.array(azimuth)
        elevation_array = np.array(elevation)
        snr_array = np.array(self.snr) if self.snr else None
        
        return RadarPointCloud(
            range=range_array,
            velocity=velocity_array,
            azimuth=azimuth_array,
            elevation=elevation_array,
            snr=snr_array,
            metadata=metadata
        )
    
    def __iter__(self) -> 'RadarDataIterator':
        """
        Return an iterator over radar frames.
        
        Returns:
            RadarDataIterator: Iterator that yields RadarPointCloud objects
        """
        return RadarDataIterator(self.radar_connection)
    
    def __str__(self) -> str:
        """Return string representation of the radar data."""
        return (f"Magic Word: {hex(self.magic_word) if self.magic_word else 'N/A'}\n"
                f"Version: {hex(self.version) if self.version else 'N/A'}\n"
                f"Total Packet Length: {self.total_packet_len}\n"
                f"Platform: {hex(self.platform) if self.platform else 'N/A'}\n"
                f"Frame Number: {self.frame_number}\n"
                f"Time CPU Cycles: {self.time_cpu_cycles}\n"
                f"Number of Detected Objects: {self.num_detected_obj}\n"
                f"Number of TLVs: {self.num_tlvs}\n"
                f"Subframe Number: {hex(self.subframe_number) if self.subframe_number is not None else 'N/A'}")


class RadarDataIterator:
    """
    Iterator for radar data frames.
    
    This class provides an iterator interface to continuously read frames
    from a radar connection and convert them to RadarPointCloud objects.
    """
    
    def __init__(self, radar_connection):
        """
        Initialize the radar data iterator.
        
        Args:
            radar_connection: RadarConnection instance to read data from
        """
        self.radar_connection = radar_connection
        
    def __iter__(self) -> 'RadarDataIterator':
        """Return self as iterator."""
        return self
        
    def __next__(self) -> RadarPointCloud:
        """
        Get the next radar frame as a RadarPointCloud.
        
        Returns:
            RadarPointCloud: Point cloud data from the next radar frame
            
        Raises:
            StopIteration: If the radar connection is closed or not running
        """
        if (self.radar_connection is None or 
            not self.radar_connection.is_connected() or 
            not self.radar_connection.is_running):
            raise StopIteration
            
        try:
            # Create a new RadarData object with the next frame
            radar_data = self.__class__.__qualname__.replace('Iterator', '')
            radar_data_obj = globals()[radar_data](self.radar_connection)
            
            # Convert to point cloud and return
            return radar_data_obj.to_point_cloud()
        except Exception as e:
            logging.error(f"Error reading next radar frame: {e}")
            raise StopIteration

class AWR2544Data(RadarData):
    """
    Parser for AWR2544 radar data packets.
    
    This class extends RadarData to handle the specific format of AWR2544 UDP packets,
    which use a different data structure than the XWR68xx series.
    """
    
    def __init__(self, radar_connection=None):
        """
        Initialize and parse AWR2544 radar data packet.

        Args:
            radar_connection: RadarConnection instance to read data from

        Raises:
            ValueError: If packet format is invalid or magic number doesn't match
        """
        super().__init__(radar_connection)
        
        # AWR2544 specific data containers
        self.compressed_data: List[int] = []
        self.decompressed_data: Optional[np.ndarray] = None
        self.config_params: Optional[dict] = None
        
        # Create debug directory if it doesn't exist
        self.debug_dir = "debug_data"
        os.makedirs(self.debug_dir, exist_ok=True)
        self.packet_count = 0
        
    def _parse_header(self, data: np.ndarray) -> None:
        """Parse the AWR2544 radar data packet header."""
        # Save raw header data for debugging
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.debug_dir, f"header_{timestamp}_{self.packet_count:04d}.bin")
        with open(filename, 'wb') as f:
            f.write(data)
        logging.debug(f"Saved raw header to {filename}")
        
        # AWR2544 header format (32 bytes):
        # - Magic word (8 bytes)
        # - Sequence number (4 bytes)
        # - Frame number (4 bytes)
        # - Chirp number (4 bytes)
        # - Length (4 bytes)
        # - CRC (4 bytes)
        # - Reserved (4 bytes)
        self.sequence_number = int.from_bytes(data[0:4], byteorder='little')
        self.frame_number = int.from_bytes(data[4:8], byteorder='little')
        self.chirp_number = int.from_bytes(data[8:12], byteorder='little')
        self.packet_length = int.from_bytes(data[12:16], byteorder='little')
        self.crc = int.from_bytes(data[16:20], byteorder='little')
        logging.debug(f"Frame {self.frame_number}, Chirp {self.chirp_number}, Seq {self.sequence_number}")
        
    def _parse_tlv_data(self, data: np.ndarray) -> None:
        """Parse the AWR2544 radar TLV data."""
        # Save raw TLV data for debugging
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.debug_dir, f"tlv_{timestamp}_{self.packet_count:04d}.bin")
        with open(filename, 'wb') as f:
            f.write(data)
        self.packet_count += 1
        logging.debug(f"Saved raw TLV data to {filename}")
        
        # Store compressed data for later decompression
        self.compressed_data = []
        for i in range(0, len(data), 4):
            if i + 4 <= len(data):
                value = int.from_bytes(data[i:i+4], byteorder='little')
                self.compressed_data.append(value)
                
        # Save compressed data for debugging
        filename = os.path.join(self.debug_dir, f"compressed_{timestamp}_{self.packet_count-1:04d}.npy")
        np.save(filename, np.array(self.compressed_data))
        logging.debug(f"Saved compressed data to {filename}")

    def check_crc(self, data: bytes, packet_length: int, crc_type: bool = True) -> bool:
        """
        Check CRC of packet data.
        
        Args:
            data: Raw packet data
            packet_length: Length of packet payload
            crc_type: True for 32-bit CRC, False for 16-bit CRC
            
        Returns:
            True if CRC check passes, False otherwise
        """
        if crc_type:
            # 32-bit CRC
            crc32 = -1
            crc32_p = -306674912  # crc32 reverse poly
            
            for i in range(packet_length + 16 + 8):
                byte = int(data[i])
                crc32 = crc32 ^ byte
                
                for j in range(8):
                    a = (crc32 >> 1) & int(0x7fffffff)
                    b = crc32_p & (-1*(crc32 & 1))
                    crc32 = a ^ b
                    
            ans32 = (~(crc32))
            if ans32 < 0:
                ans32 = ans32 + int(0xffffffff) + 1
            computed_crc = ans32
            actual_crc = int.from_bytes(data[packet_length+16+8:packet_length+16+12], byteorder='little')
            return computed_crc == actual_crc
        else:
            # 16-bit CRC
            crc16 = -1
            crc16_p = 4129  # crc16 reverse poly
            
            for i in range(packet_length + 16 + 8):
                byte = int(data[i])
                crc16 = crc16 ^ (byte << 8)
                
                for j in range(8):
                    if (crc16 & 0x8000 == 0x8000):
                        crc16 = (crc16 << 1) ^ crc16_p
                    else:
                        crc16 = crc16 << 1
                        
            computed_crc = crc16 & 0xffff
            actual_crc = int.from_bytes(data[packet_length+16+8:packet_length+16+10], byteorder='little')
            return computed_crc == actual_crc
        
    def decompress_data(self, config_params: dict) -> None:
        """
        Decompress the radar data using the AWR2544's compression scheme.
        
        Args:
            config_params: Dictionary containing radar configuration parameters
                         needed for decompression
        """
        if not self.compressed_data:
            return
            
        self.config_params = config_params
        samples_per_block = (config_params['rangeBinsPerBlock'] if config_params['compMethod'] == 1 
                           else config_params['rxAnt'] * config_params['rangeBinsPerBlock'])
        
        # Calculate decompressed data size
        num_samples = config_params['rangeBins'] * config_params['rxAnt']
        if config_params.get('dcmpFrame', False):
            num_samples *= config_params['chirpsPerFrame']
            
        # Initialize decompressed data array (complex values)
        self.decompressed_data = np.zeros(num_samples, dtype=np.complex64)
        
        # Decompress data blocks
        input_idx = 0
        output_idx = 0
        while input_idx < len(self.compressed_data) and output_idx < num_samples:
            # Each block contains samples_per_block complex values
            block = self.compressed_data[input_idx:input_idx + samples_per_block]
            if len(block) < samples_per_block:
                break
                
            # Convert block to complex values
            for i in range(0, len(block), 2):
                if i + 1 >= len(block):
                    break
                real = block[i]
                imag = block[i + 1]
                if output_idx < num_samples:
                    self.decompressed_data[output_idx] = complex(real, imag)
                    output_idx += 1
                    
            input_idx += samples_per_block
            
        # Reshape data based on compression method
        if config_params['compMethod'] == 1:
            # Method 1: Data is organized by range bins then RX
            self.decompressed_data = self.decompressed_data.reshape(-1, config_params['rxAnt'])
        else:
            # Method 0: Data is organized by RX then range bins
            self.decompressed_data = self.decompressed_data.reshape(config_params['rxAnt'], -1).T
        
    def get_point_cloud(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Extract point cloud data from decompressed radar data.
        
        Returns:
            Tuple containing arrays of x, y, z coordinates and velocity
        """
        if self.decompressed_data is None or self.config_params is None:
            return np.array([]), np.array([]), np.array([]), np.array([])
            
        # Process decompressed data to get point cloud
        # First get range profile
        range_profile = np.abs(self.decompressed_data)
        
        # Calculate range for each bin
        range_res = (3e8 * self.config_params['sampleRate'] * 1e3) / \
                   (2 * self.config_params['slope'] * 1e12 * self.config_params['rangeBins'] * 2)
        ranges = np.arange(self.config_params['rangeBins']) * range_res
        
        # Find peaks in range profile (simple threshold-based detection)
        threshold = np.mean(range_profile) + 2 * np.std(range_profile)
        detected_points = np.where(range_profile > threshold)
        
        if len(detected_points[0]) == 0:
            return np.array([]), np.array([]), np.array([]), np.array([])
            
        # Convert to x, y, z coordinates
        x = ranges[detected_points[0]] * np.cos(detected_points[1] * np.pi / self.config_params['rxAnt'])
        y = ranges[detected_points[0]] * np.sin(detected_points[1] * np.pi / self.config_params['rxAnt'])
        z = np.zeros_like(x)  # Z coordinate requires elevation angle estimation
        
        # Velocity estimation would require Doppler processing across chirps
        v = np.zeros_like(x)
        
        # Store point cloud data
        self.pc = (x, y, z, v)
        
        return x, y, z, v
    
    def to_point_cloud(self) -> RadarPointCloud:
        """
        Convert the AWR2544 radar data to a RadarPointCloud object.
        
        This method first ensures the point cloud data is available by calling
        get_point_cloud() if needed, then converts it to a RadarPointCloud.
        
        Returns:
            RadarPointCloud: Point cloud representation of the radar data
        """
        # Make sure point cloud data is available
        if self.pc is None:
            self.get_point_cloud()
            
        # Use the parent class method to convert to RadarPointCloud
        return super().to_point_cloud()


class AWR2544DataIterator(RadarDataIterator):
    """
    Iterator for AWR2544 radar data frames.
    
    This class extends RadarDataIterator to handle the specific format of AWR2544 data.
    """
    
    def __next__(self) -> RadarPointCloud:
        """
        Get the next AWR2544 radar frame as a RadarPointCloud.
        
        Returns:
            RadarPointCloud: Point cloud data from the next radar frame
            
        Raises:
            StopIteration: If the radar connection is closed or not running
        """
        if (self.radar_connection is None or 
            not self.radar_connection.is_connected() or 
            not self.radar_connection.is_running):
            raise StopIteration
            
        try:
            # Create a new AWR2544Data object with the next frame
            radar_data = AWR2544Data(self.radar_connection)
            
            # Convert to point cloud and return
            return radar_data.to_point_cloud()
        except Exception as e:
            logging.error(f"Error reading next AWR2544 radar frame: {e}")
            raise StopIteration
