import numpy as np
import struct
from typing import Tuple, List, Optional
import time
import logging

# Magic number for radar data validation
MAGIC_NUMBER = 0x708050603040102

class RadarData:
    """
    Parser for TI mmWave radar data packets.
    
    This class handles parsing of binary data packets from TI mmWave radar sensors,
    extracting point cloud data, range profiles, and side information.
    
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
    
    # TLV message types
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS = 1
    MMWDEMO_OUTPUT_MSG_RANGE_PROFILE = 2
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO = 7

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
        
        if radar_connection is None or not radar_connection.is_connected():
            return
            
        header = radar_connection.read_header()
        if header is not None:
            assert len(header) == 32
            self._parse_header(header)
            payload = radar_connection.read_packet(self.total_packet_len)
            if payload is not None:
                self._parse_tlv_data(payload)

    def _parse_header(self, data: np.ndarray) -> None:
        """Parse the radar data packet header."""
        self.version = int.from_bytes(data[0:4], byteorder='little')
        self.total_packet_len = int.from_bytes(data[4:8], byteorder='little')
        logging.debug(f"Total packet length: {self.total_packet_len}")
        self.platform = int.from_bytes(data[8:12], byteorder='little')
        self.frame_number = int.from_bytes(data[12:16], byteorder='little')
        logging.debug(f"Frame number: {self.frame_number}")
        self.time_cpu_cycles = int.from_bytes(data[16:20], byteorder='little')
        self.num_detected_obj = int.from_bytes(data[20:24], byteorder='little')
        self.num_tlvs = int.from_bytes(data[24:28], byteorder='little')
        self.subframe_number = (int.from_bytes(data[28:32], byteorder='little') 
                              if self.num_detected_obj > 0 else None)

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
        length = tlv_length // 2
#        self.adc = np.frombuffer(data[idx:idx+tlv_length], dtype=np.uint16)
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

    def __str__(self) -> str:
        """Return string representation of the radar data."""
        return (f"Magic Word: {hex(self.magic_word)}\n"
                f"Version: {hex(self.version)}\n"
                f"Total Packet Length: {self.total_packet_len}\n"
                f"Platform: {hex(self.platform)}\n"
                f"Frame Number: {self.frame_number}\n"
                f"Time CPU Cycles: {self.time_cpu_cycles}\n"
                f"Number of Detected Objects: {self.num_detected_obj}\n"
                f"Number of TLVs: {self.num_tlvs}\n"
                f"Subframe Number: {hex(self.subframe_number) if self.subframe_number is not None else 'N/A'}")
