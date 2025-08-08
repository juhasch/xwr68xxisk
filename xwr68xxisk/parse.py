import numpy as np
import logging
import struct
from typing import Optional, Tuple, List, Iterator, Dict, Any
import time
import os
import math
from .point_cloud import RadarPointCloud
import logging

logger = logging.getLogger(__name__)

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
        adc (np.ndarray): Range profile data (log magnitude)
        adc_complex (np.ndarray): Complex range profile data (raw complex values)
        side_info (Tuple[List[float], List[float]]): SNR and noise data
        snr (List[float]): Signal-to-noise ratio for each point
        noise (List[float]): Noise level for each point
        range_doppler_heatmap (np.ndarray): Range-Doppler heat map matrix (range bins × Doppler bins)
        noise_profile (np.ndarray): Noise profile data
    """
    
    # TLV (Type-Length-Value) types
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS = 1
    MMWDEMO_OUTPUT_MSG_RANGE_PROFILE = 2
    MMWDEMO_OUTPUT_MSG_NOISE_PROFILE = 3
    MMWDEMO_OUTPUT_MSG_AZIMUT_STATIC_HEAT_MAP = 4
    MMWDEMO_OUTPUT_MSG_RANGE_DOPPLER_HEAT_MAP = 5
    MMWDEMO_OUTPUT_MSG_STATS = 6
    MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO = 7
    MMWDEMO_OUTPUT_MSG_AZIMUT_ELEVATION_STATIC_HEAT_MAP = 8
    MMWDEMO_OUTPUT_MSG_TEMPERATURE_STATS = 9
    MMWDEMO_OUTPUT_MSG_RANGE_PROFILE_COMPLEX = 10
  
    def __init__(self, radar_connection=None, config_params: Dict[str, Any] = None):
        """Initialize RadarData parser.
        
        Args:
            radar_connection: Connection to the radar sensor
            config_params: Configuration parameters for parsing
        """
        self.radar_connection = radar_connection
        self.config_params = config_params or {}
        
        # Header information
        self.magic_word = None
        self.version = None
        self.total_packet_len = None
        self.platform = None
        self.frame_number = None
        self.time_cpu_cycles = None
        self.num_detected_obj = None
        self.num_tlvs = None
        
        # Data arrays
        self.pc = ([], [], [], [])  # Point cloud (x, y, z, velocity)
        self.adc = None  # Range profile data (log magnitude)
        self.adc_complex = None  # Complex range profile data
        self.side_info = ([], [])  # SNR and noise data
        self.snr = []
        self.noise = []
        self.range_doppler_heatmap = None
        self.azimuth_heatmap = None
        self.noise_profile: Optional[np.ndarray] = None
        self.stats_data = None
        self.temperature_stats_data = None
        
        if radar_connection is None or not radar_connection.is_connected() or not radar_connection.is_running:
            return
            
        try:
            frame_data = radar_connection.read_frame()
            if frame_data is None:
                logging.warning("No frame data received from radar")
                return
                
            header, payload = frame_data
            if header is not None and payload is not None:
                self.frame_number = header.get('frame_number')
                self.num_tlvs = header.get('num_tlvs', 0)  # Changed from num_detected_obj to num_tlvs
                
                # Ensure we have valid payload data
                if len(payload) == 0:
                    logging.warning("Empty payload received from radar")
                    return
                    
                try:
                    self._parse_tlv_data(payload)
                except Exception as tlv_error:
                    logging.error(f"Error parsing TLV data: {tlv_error}")
                    # Ensure azimuth_heatmap is initialized even if parsing fails
                    if not hasattr(self, 'azimuth_heatmap') or self.azimuth_heatmap is None:
                        self.azimuth_heatmap = np.array([])
            else:
                logging.warning("Header information is missing")
        except Exception as e:
            logging.error(f"Error reading radar data: {e}")
            # Ensure azimuth_heatmap is initialized even if reading fails
            if not hasattr(self, 'azimuth_heatmap') or self.azimuth_heatmap is None:
                self.azimuth_heatmap = np.array([])
            return

    def _parse_tlv_data(self, data: np.ndarray) -> None:
        """Parse TLV (Type-Length-Value) data from the radar packet."""
        data_bytes = data
        idx = 0  # Start after header
       
       
        for tlv_idx in range(self.num_tlvs):
            if idx + 8 > len(data_bytes):  # Check if we have enough data to read TLV header
                logging.warning(f"Insufficient data for TLV header at position {idx}, available: {len(data_bytes) - idx} bytes")
                break
                
            tlv_type = int.from_bytes(data_bytes[idx:idx+4], byteorder='little')
            tlv_length = int.from_bytes(data_bytes[idx+4:idx+8], byteorder='little')
            idx += 8
            
            logger.debug(f"TLV {tlv_idx + 1}/{self.num_tlvs}: type={tlv_type}, length={tlv_length}")
            
            # Ensure we have enough data to process this TLV
            if idx + tlv_length > len(data_bytes):
                logging.warning(f"Insufficient data for TLV type {tlv_type} with length {tlv_length}, available: {len(data_bytes) - idx} bytes")
                # Try to process what we can with the available data
                available_length = len(data_bytes) - idx
                if available_length > 0:
                    logger.debug(f"Attempting to process TLV type {tlv_type} with available data: {available_length} bytes")
                    idx = self._parse_tlv_with_available_data(data_bytes, idx, tlv_type, available_length)
                break
                
            if tlv_type == self.MMWDEMO_OUTPUT_MSG_DETECTED_POINTS:
                logger.debug(f"Parsing point cloud data with length {tlv_length}")
                idx = self._parse_point_cloud(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_RANGE_PROFILE:
                logger.debug(f"Parsing range profile data with length {tlv_length}")
                idx = self._parse_range_profile(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_DETECTED_POINTS_SIDE_INFO:
                logger.debug(f"Parsing side info data with length {tlv_length}")
                idx = self._parse_side_info(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_RANGE_DOPPLER_HEAT_MAP:
                logger.debug(f"Parsing range-Doppler heatmap data with length {tlv_length}")
                idx = self._parse_range_doppler_heatmap(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_AZIMUT_STATIC_HEAT_MAP:
                logger.debug(f"Parsing azimuth heatmap data with length {tlv_length}")
                idx = self._parse_azimuth_heatmap(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_NOISE_PROFILE:
                logger.debug(f"Parsing noise profile data with length {tlv_length}")
                idx = self._parse_noise_profile(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_STATS:
                logger.debug(f"Parsing stats data with length {tlv_length}")
                idx = self._parse_stats(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_TEMPERATURE_STATS:
                logger.debug(f"Parsing temperature stats data with length {tlv_length}")
                idx = self._parse_temperature_stats(data_bytes, idx, tlv_length)
            elif tlv_type == self.MMWDEMO_OUTPUT_MSG_RANGE_PROFILE_COMPLEX:
                logger.debug(f"Parsing complex range profile data with length {tlv_length}")
                idx = self._parse_complex_range_profile(data_bytes, idx, tlv_length)
            else:
                logger.debug(f"Skipping unknown TLV type {tlv_type} with length {tlv_length}")
                idx += tlv_length

    def _parse_tlv_with_available_data(self, data: bytes, idx: int, tlv_type: int, available_length: int) -> int:
        """Parse TLV data with limited available data.
        
        This method is called when there's insufficient data for a complete TLV.
        It attempts to process what data is available.
        
        Args:
            data: Raw data bytes
            idx: Current index in data
            tlv_type: Type of TLV
            available_length: Length of available data
            
        Returns:
            Updated index after parsing
        """
        logger.warning(f"Processing TLV type {tlv_type} with limited data: {available_length} bytes available")
        
        # For now, just skip the available data and return
        # In the future, we could implement partial parsing for specific TLV types
        return idx + available_length

    def _parse_point_cloud(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse point cloud data from TLV."""
        # Ensure tlv_length is a multiple of 16 (each point is 16 bytes)
        usable_length = tlv_length - (tlv_length % 16)
        num_points = usable_length // 16
        
        x, y, z, v = [], [], [], []
        
        if usable_length <= 0:
            logging.warning("Point cloud data length is not a multiple of point size (16 bytes)")
            self.pc = (x, y, z, v)
            return idx + tlv_length
        
        try:
            for point in range(num_points):
                point_idx = idx + (point * 16)
                if point_idx + 16 > len(data):  # Check if we have enough data
                    logging.warning(f"Insufficient data for point cloud at point {point}")
                    break
                
                try:
                    x.append(struct.unpack('f', data[point_idx:point_idx+4])[0])
                    y.append(struct.unpack('f', data[point_idx+4:point_idx+8])[0])
                    z.append(struct.unpack('f', data[point_idx+8:point_idx+12])[0])
                    v.append(struct.unpack('f', data[point_idx+12:point_idx+16])[0])
                except struct.error as e:
                    logging.warning(f"Error unpacking point cloud data at point {point}: {e}")
                    continue
        except Exception as e:
            logging.error(f"Error processing point cloud data: {e}")
        
        self.pc = (x, y, z, v)
        return idx + tlv_length

    def _parse_range_profile(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse range profile data from TLV."""
        # Ensure tlv_length is a multiple of 2 (size of uint16)
        usable_length = tlv_length - (tlv_length % 2)
        logger.debug(f"usable_length: {usable_length}")
        if usable_length > 0:
            logger.debug("Starting to parse range profile data")
            self.adc = np.frombuffer(data[idx:idx+usable_length], dtype=np.uint16)
        else:
            logging.warning("Range profile data length is not a multiple of uint16 size")
            self.adc = np.array([], dtype=np.uint16)
        return idx + tlv_length

    def _parse_side_info(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse side information (SNR and noise) from TLV."""
        num_points = tlv_length // 4
        self.snr = []
        self.noise = []
        
        try:
            # Ensure tlv_length is a multiple of 4 (each point is 4 bytes)
            usable_length = tlv_length - (tlv_length % 4)
            usable_points = usable_length // 4
            
            if usable_points == 0:
                logging.warning("Side info data length is not a multiple of point size (4 bytes)")
                return idx + tlv_length
                
            for point in range(usable_points):
                point_idx = idx + (point * 4)
                if point_idx + 4 > len(data):  # Check if we have enough data
                    logging.warning(f"Insufficient data for side info at point {point}: needed 4 bytes, had {len(data) - point_idx}")
                    break
                    
                try:
                    snr_val = struct.unpack('h', data[point_idx:point_idx+2])[0] * 0.1
                    noise_val = struct.unpack('h', data[point_idx+2:point_idx+4])[0] * 0.1
                    self.snr.append(snr_val)
                    self.noise.append(noise_val)
                except struct.error as e:
                    logging.warning(f"Error unpacking side info at point {point}: {e}")
                    continue
                
        except Exception as e:
            logging.warning(f"Error processing side info data: {e}")
            self.snr = []
            self.noise = []
        
        return idx + tlv_length

    def _parse_range_doppler_heatmap(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse range-Doppler heat map data from TLV.
        
        The heat map is a log magnitude range-Doppler matrix stored as uint16_t values.
        Size = number of range bins × number of Doppler bins
        
        Args:
            data: Raw data bytes
            idx: Current index in data
            tlv_length: Length of TLV data in bytes
            
        Returns:
            Updated index after parsing
        """
        # Calculate dimensions based on TLV length and uint16 size
        total_bins = tlv_length // 2  # Each bin is 2 bytes (uint16)
        
        # Ensure tlv_length is a multiple of 2 (size of uint16)
        usable_length = tlv_length - (tlv_length % 2)
        
        if usable_length <= 0:
            logging.warning("Range-Doppler heatmap data length is not a multiple of uint16 size")
            self.range_doppler_heatmap = np.array([], dtype=np.uint16)
            return idx + tlv_length
        
        try:
            # Create numpy array from raw bytes
            heatmap = np.frombuffer(data[idx:idx+usable_length], dtype=np.uint16)
            
            # Get dimensions from radar configuration
            num_range_bins = self.config_params.get('rangeBins', 256)  # Default from config files
            num_doppler_bins = self.config_params.get('num_doppler_bins', 32)  # Default to 32 if not found
            
            logger.debug(f"num_range_bins: {num_range_bins}, num_doppler_bins: {num_doppler_bins}")

            # Verify dimensions match the data
            if total_bins == num_range_bins * num_doppler_bins:
                # Reshape using actual dimensions
                self.range_doppler_heatmap = heatmap.reshape(num_range_bins, num_doppler_bins)
                logger.debug(f"Successfully parsed range-Doppler heatmap: {num_range_bins}x{num_doppler_bins}")
            else:
                # Log warning and try to infer dimensions
                logging.warning(f"Range-Doppler heatmap dimensions mismatch. Expected {num_range_bins}x{num_doppler_bins} bins but got {total_bins} total bins.")
                
                # Try to infer dimensions from the data
                if total_bins % num_range_bins == 0:
                    inferred_doppler_bins = total_bins // num_range_bins
                    logging.info(f"Inferred {inferred_doppler_bins} Doppler bins from data (expected {num_doppler_bins})")
                    self.range_doppler_heatmap = heatmap.reshape(num_range_bins, inferred_doppler_bins)
                else:
                    # Use square matrix as fallback
                    dim = int(np.sqrt(total_bins))
                    if dim * dim == total_bins:
                        self.range_doppler_heatmap = heatmap.reshape(dim, dim)
                        logging.warning(f"Using square heatmap: {dim}x{dim}")
                    else:
                        # Last resort: use as 1D array
                        self.range_doppler_heatmap = heatmap.reshape(1, -1)
                        logging.warning(f"Using 1D heatmap: 1x{total_bins}")
                        
        except Exception as e:
            logging.error(f"Error processing range-Doppler heatmap: {e}")
            self.range_doppler_heatmap = np.array([], dtype=np.uint16)
        
        return idx + tlv_length

    def _parse_azimuth_heatmap(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse azimuth static heat map data from TLV.
        
        According to TI documentation, the data format is:
        - Length: (Range FFT size) × (Number of virtual antennas)
        - Data: Complex symbols with imaginary first, real second
        - Order: Imag(ant 0, range 0), Real(ant 0, range 0), ..., Imag(ant N-1, range 0), Real(ant N-1, range 0)
        
        Args:
            data: Raw data bytes
            idx: Current index in data
            tlv_length: Length of TLV data in bytes
            
        Returns:
            Updated index after parsing
        """
        # Check if we have enough data for this TLV
        if idx + tlv_length > len(data):
            logging.warning(f"Insufficient data for azimuth heatmap TLV: need {tlv_length} bytes, have {len(data) - idx} bytes")
            self.azimuth_heatmap = np.array([])
            return len(data)  # Return end of available data
        
        # Each complex value is 4 bytes (2 bytes imag + 2 bytes real)
        total_complex_values = tlv_length // 4
        
        if tlv_length % 4 != 0:
            logging.warning("Azimuth heatmap data length is not a multiple of complex value size (4 bytes)")
            self.azimuth_heatmap = np.array([])
            return idx + tlv_length
        
        try:
            # Create numpy array from raw bytes as int16 (2 bytes per value)
            complex_data = np.frombuffer(data[idx:idx+tlv_length], dtype=np.int16)
            
            # Get dimensions from radar configuration
            num_range_bins = self.config_params.get('rangeBins', 256)
            num_virtual_antennas = self.config_params.get('numVirtualAntennas', 4)  # Default for typical configurations
            
            # Verify dimensions match the data
            expected_complex_values = num_range_bins * num_virtual_antennas
            if total_complex_values == expected_complex_values:
                # Reshape to (range_bins, num_virtual_antennas, 2) where 2 represents [imag, real]
                heatmap_complex = complex_data.reshape(num_range_bins, num_virtual_antennas, 2)
                
                # Convert to complex numbers: imag + j*real
                heatmap = heatmap_complex[:, :, 0].astype(np.float32) + 1j * heatmap_complex[:, :, 1].astype(np.float32)
                
                # Take magnitude for visualization
                self.azimuth_heatmap = np.abs(heatmap)
                logger.debug(f"Successfully parsed azimuth heatmap: {num_range_bins}x{num_virtual_antennas}")
            else:
                # Try to infer dimensions from the data
                if total_complex_values % num_range_bins == 0:
                    inferred_antennas = total_complex_values // num_range_bins
                    logging.info(f"Inferred {inferred_antennas} virtual antennas from data (expected {num_virtual_antennas})")
                    
                    # Reshape with inferred dimensions
                    heatmap_complex = complex_data.reshape(num_range_bins, inferred_antennas, 2)
                    heatmap = heatmap_complex[:, :, 0].astype(np.float32) + 1j * heatmap_complex[:, :, 1].astype(np.float32)
                    self.azimuth_heatmap = np.abs(heatmap)
                    logger.debug(f"Successfully parsed azimuth heatmap with inferred dimensions: {num_range_bins}x{inferred_antennas}")
                else:
                    logging.warning(f"Azimuth heatmap dimensions mismatch. Expected {num_range_bins}x{num_virtual_antennas} complex values but got {total_complex_values} total values.")
                    # Try to create a reasonable heatmap anyway
                    if total_complex_values > 0:
                        # Try to make it square-ish
                        side_length = int(np.sqrt(total_complex_values))
                        if side_length * side_length == total_complex_values:
                            # Perfect square
                            heatmap_complex = complex_data.reshape(side_length, side_length, 2)
                            heatmap = heatmap_complex[:, :, 0].astype(np.float32) + 1j * heatmap_complex[:, :, 1].astype(np.float32)
                            self.azimuth_heatmap = np.abs(heatmap)
                            logger.warning(f"Created square azimuth heatmap: {side_length}x{side_length}")
                        else:
                            # Not a perfect square, use as 1D array
                            self.azimuth_heatmap = np.array([])
                            logger.warning(f"Could not create reasonable azimuth heatmap from {total_complex_values} complex values")
                    else:
                        self.azimuth_heatmap = np.array([])
        except Exception as e:
            logging.error(f"Error processing azimuth heatmap: {e}")
            self.azimuth_heatmap = np.array([])
        
        return idx + tlv_length

    def _parse_noise_profile(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse noise profile data from TLV."""
        # Ensure tlv_length is a multiple of 2 (size of uint16)
        usable_length = tlv_length - (tlv_length % 2)
        logger.debug(f"usable_length: {usable_length}")
        if usable_length > 0:
            logger.debug("Starting to parse noise profile data")
            self.noise_profile = np.frombuffer(data[idx:idx+usable_length], dtype=np.uint16)
        else:
            logging.warning("Noise profile data length is not a multiple of uint16 size")
            self.noise_profile = np.array([], dtype=np.uint16)
        return idx + tlv_length

    def _parse_stats(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse stats data from TLV.
        
        Based on MmwDemo_output_message_stats_t structure:
        - interFrameProcessingTime (uint32_t): Interframe processing time in usec
        - transmitOutputTime (uint32_t): Transmission time of output detection information in usec
        - interFrameProcessingMargin (uint32_t): Interframe processing margin in usec
        - interChirpProcessingMargin (uint32_t): Interchirp processing margin in usec
        - activeFrameCPULoad (uint32_t): CPU Load (%) during active frame duration
        - interFrameCPULoad (uint32_t): CPU Load (%) during inter frame duration
        """
        logger.debug(f"Parsing stats data with length {tlv_length}")
        
        # Store the raw data for debugging
        raw_data = data[idx:idx+tlv_length]
        self.stats_data = raw_data
        
        if tlv_length == 24:  # 6 uint32_t values
            # Parse according to MmwDemo_output_message_stats_t structure
            inter_frame_processing_time = int.from_bytes(raw_data[0:4], byteorder='little')
            transmit_output_time = int.from_bytes(raw_data[4:8], byteorder='little')
            inter_frame_processing_margin = int.from_bytes(raw_data[8:12], byteorder='little')
            inter_chirp_processing_margin = int.from_bytes(raw_data[12:16], byteorder='little')
            active_frame_cpu_load = int.from_bytes(raw_data[16:20], byteorder='little')
            inter_frame_cpu_load = int.from_bytes(raw_data[20:24], byteorder='little')
            
            logger.info(f"Stats data:")
            logger.info(f"  Inter-frame processing time: {inter_frame_processing_time} usec")
            logger.info(f"  Transmit output time: {transmit_output_time} usec")
            logger.info(f"  Inter-frame processing margin: {inter_frame_processing_margin} usec")
            logger.info(f"  Inter-chirp processing margin: {inter_chirp_processing_margin} usec")
            logger.info(f"  Active frame CPU load: {active_frame_cpu_load}%")
            logger.info(f"  Inter-frame CPU load: {inter_frame_cpu_load}%")
        else:
            # Unknown structure, log as hex
            hex_data = raw_data.hex()
            logger.info(f"Stats data (unknown structure, {tlv_length} bytes): {hex_data}")
        
        return idx + tlv_length

    def _parse_temperature_stats(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse temperature stats data from TLV.
        
        Based on MmwDemo_temperatureStats_t structure:
        - tempReportValid (int32_t): Return value from API rlRfTempData_t (0 = valid, non-zero = invalid)
        - temperatureReport (rlRfTempData_t): Detailed temperature report
        
        The rlRfTempData_t structure contains:
        - time (uint32_t): radarSS local Time from device powerup. 1 LSB = 1 ms
        - tmpRx0Sens (int16_t): RX0 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpRx1Sens (int16_t): RX1 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpRx2Sens (int16_t): RX2 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpRx3Sens (int16_t): RX3 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpTx0Sens (int16_t): TX0 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpTx1Sens (int16_t): TX1 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpTx2Sens (int16_t): TX2 temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpPmSens (int16_t): PM temperature sensor reading (signed value). 1 LSB = 1 deg C
        - tmpDig0Sens (int16_t): Digital temp sensor reading (signed value). 1 LSB = 1 deg C
        - tmpDig1Sens (int16_t): Second digital temp sensor reading (signed value). 1 LSB = 1 deg C
        """
        logger.debug(f"Parsing temperature stats data with length {tlv_length}")
        
        # Store the raw data for debugging
        raw_data = data[idx:idx+tlv_length]
        self.temperature_stats_data = raw_data
        
        # Parse tempReportValid (first 4 bytes)
        if tlv_length >= 4:
            temp_report_valid = int.from_bytes(raw_data[0:4], byteorder='little', signed=True)
            logger.info(f"Temperature stats data:")
            logger.info(f"  Temperature report valid: {temp_report_valid}")
            
            # Parse the remaining data (24 bytes) as rlRfTempData_t structure
            if tlv_length == 28:  # Expected size: 4 bytes int32 + 24 bytes rlRfTempData_t
                remaining_data = raw_data[4:]
                
                if len(remaining_data) == 24:
                    # Parse according to rlRfTempData_t structure
                    time_ms = int.from_bytes(remaining_data[0:4], byteorder='little')
                    
                    # Parse 10 temperature sensors (each 2 bytes, signed int16)
                    temp_sensors = []
                    for i in range(4, 24, 2):
                        temp_val = int.from_bytes(remaining_data[i:i+2], byteorder='little', signed=True)
                        temp_sensors.append(temp_val)
                    
                    logger.info(f"  Time from powerup: {time_ms} ms")
                    logger.info(f"  Temperature sensors (deg C):")
                    logger.info(f"    RX0: {temp_sensors[0]}°C")
                    logger.info(f"    RX1: {temp_sensors[1]}°C")
                    logger.info(f"    RX2: {temp_sensors[2]}°C")
                    logger.info(f"    RX3: {temp_sensors[3]}°C")
                    logger.info(f"    TX0: {temp_sensors[4]}°C")
                    logger.info(f"    TX1: {temp_sensors[5]}°C")
                    logger.info(f"    TX2: {temp_sensors[6]}°C")
                    logger.info(f"    PM:  {temp_sensors[7]}°C")
                    logger.info(f"    Dig0: {temp_sensors[8]}°C")
                    logger.info(f"    Dig1: {temp_sensors[9]}°C")
                    
                    # Also show the raw uint16 interpretation for comparison
                    uint16_values = []
                    for i in range(4, 24, 2):
                        val = int.from_bytes(remaining_data[i:i+2], byteorder='little')
                        uint16_values.append(val)
                    logger.info(f"  Raw uint16 values: {uint16_values}")
                        
                else:
                    logger.warning(f"Unexpected temperature data length: {len(remaining_data)} bytes")
                    hex_data = ' '.join(f'{b:02x}' for b in remaining_data)
                    logger.info(f"Temperature stats data (unknown structure, {len(remaining_data)} bytes): {hex_data}")
            else:
                logger.warning(f"Unexpected TLV length for temperature stats: {tlv_length} bytes")
                hex_data = ' '.join(f'{b:02x}' for b in raw_data)
                logger.info(f"Temperature stats data (unknown structure, {tlv_length} bytes): {hex_data}")
        else:
            logger.warning(f"Temperature stats TLV too short: {tlv_length} bytes")
            hex_data = ' '.join(f'{b:02x}' for b in raw_data)
            logger.info(f"Temperature stats data (too short, {tlv_length} bytes): {hex_data}")
        
        return idx + tlv_length

    def _parse_complex_range_profile(self, data: bytes, idx: int, tlv_length: int) -> int:
        """Parse complex range profile data from TLV.
        
        The complex data format follows the cmplx16ImRe_t structure:
        - Each complex value is 4 bytes (2 bytes imag + 2 bytes real)
        - Data represents 0th Doppler bin (stationary objects) for each range bin
        - Byte order is little-endian
        
        Args:
            data: Raw data bytes
            idx: Current index in data
            tlv_length: Length of TLV data in bytes
            
        Returns:
            Updated index after parsing
        """
        # Each complex value is 4 bytes (2 bytes imag + 2 bytes real)
        total_complex_values = tlv_length // 4
        
        if tlv_length % 4 != 0:
            logging.warning("Complex range profile data length is not a multiple of complex value size (4 bytes)")
            self.adc_complex = np.array([])
            return idx + tlv_length
        
        try:
            # Create numpy array from raw bytes as int16 (2 bytes per value)
            complex_data = np.frombuffer(data[idx:idx+tlv_length], dtype=np.int16)
            
            # Get number of range bins from configuration
            num_range_bins = self.config_params.get('rangeBins', 256)
            
            # Verify dimensions match the data
            if total_complex_values == num_range_bins:
                # Reshape to (num_range_bins, 2) where 2 represents [imag, real]
                complex_reshaped = complex_data.reshape(num_range_bins, 2)
                
                # Convert to complex numbers: imag + j*real
                # Note: The data format is [imag, real] pairs
                self.adc_complex = complex_reshaped[:, 0].astype(np.float32) + 1j * complex_reshaped[:, 1].astype(np.float32)
                
                logger.debug(f"Parsed complex range profile: {num_range_bins} range bins")
            else:
                logging.warning(f"Complex range profile dimensions mismatch. Expected {num_range_bins} complex values but got {total_complex_values} total values.")
                # Try to use the data as-is if dimensions don't match
                if len(complex_data) >= 2:
                    # Reshape to pairs of [imag, real]
                    num_pairs = len(complex_data) // 2
                    complex_reshaped = complex_data[:num_pairs*2].reshape(num_pairs, 2)
                    self.adc_complex = complex_reshaped[:, 0].astype(np.float32) + 1j * complex_reshaped[:, 1].astype(np.float32)
                    logger.warning(f"Using {num_pairs} complex values from data")
                else:
                    self.adc_complex = np.array([])
                    
        except Exception as e:
            logging.error(f"Error processing complex range profile: {e}")
            self.adc_complex = np.array([])
        
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
        snr_array = np.array(self.snr) if self.snr else np.zeros(len(range_values))
        
        # Calculate RCS values based on SNR and range
        # This is a simplified model; actual RCS calculation would depend on radar parameters
        if snr_array is not None and len(snr_array) > 0:
            # Convert SNR from dB to linear scale with clipping to prevent overflow
            snr_db = np.clip(snr_array, -100, 100)  # Limit SNR range to prevent overflow
            snr_linear = np.power(10.0, snr_db/10.0)
            # RCS is proportional to SNR * range^4 (radar equation)
            # This is a simplified calculation for demonstration
            rcs_array = snr_linear * np.power(range_array, 4) / 1e6  # Scaling factor
            # Convert back to dB scale
            rcs_array = 10 * np.log10(np.maximum(rcs_array, 1e-10))
        else:
            rcs_array = np.zeros(len(range_values))
        
        return RadarPointCloud(
            range=range_array,
            velocity=velocity_array,
            azimuth=azimuth_array,
            elevation=elevation_array,
            snr=snr_array,
            rcs=rcs_array,
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

    def get_range_doppler_heatmap(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get the range-Doppler heatmap with proper scaling and axes.
        
        Returns:
            Tuple containing:
            - 2D numpy array of heatmap values in dB
            - 1D numpy array of range values in meters
            - 1D numpy array of velocity values in m/s
        """
        if self.range_doppler_heatmap is None:
            return np.array([]), np.array([]), np.array([])
        
        # Check if heatmap has valid shape
        if len(self.range_doppler_heatmap.shape) != 2:
            logger.warning(f"Range-Doppler heatmap has invalid shape: {self.range_doppler_heatmap.shape}")
            return np.array([]), np.array([]), np.array([])
            
        # Get radar parameters
        num_range_bins = self.config_params.get('rangeBins', 256)
        range_resolution = self.config_params.get('rangeStep')
        
        if range_resolution is None:
            logger.warning("rangeStep not found in config_params, using default 0.044 m/bin")
            range_resolution = 0.044  # Default from profile
        
        # Calculate velocity resolution from chirp parameters
        chirp_duration = self.config_params.get('rampEndTime', 60) * 1e-6  # Convert μs to seconds
        chirps_per_frame = self.config_params.get('chirpsPerFrame', 32)
        wavelength = 3e8 / (77e9)  # Speed of light / radar frequency (assuming 77 GHz)
        velocity_resolution = wavelength / (4 * chirp_duration * chirps_per_frame)  # m/s per bin
        
        # Create range and velocity axes
        range_axis = np.arange(num_range_bins) * range_resolution
        num_doppler_bins = self.range_doppler_heatmap.shape[1]
        velocity_axis = np.linspace(-num_doppler_bins//2, num_doppler_bins//2-1, num_doppler_bins) * velocity_resolution
        
        logger.debug(f"Range-Doppler heatmap: range_axis from 0 to {range_axis[-1]:.3f} m, velocity_axis from {velocity_axis[0]:.3f} to {velocity_axis[-1]:.3f} m/s")
        
        # Check for invalid data
        if np.any(np.isnan(self.range_doppler_heatmap)) or np.any(np.isinf(self.range_doppler_heatmap)):
            logger.warning("Range-Doppler heatmap contains NaN or Inf values")
            return np.array([]), np.array([]), np.array([])
        
        # Convert heatmap values to dB (assuming they are linear magnitude)
        try:
            heatmap_db = 20 * np.log10(self.range_doppler_heatmap.astype(np.float32) + 1)  # Add 1 to avoid log(0)
            return heatmap_db, range_axis, velocity_axis
        except Exception as e:
            logger.error(f"Error converting range-Doppler heatmap to dB: {e}")
            return np.array([]), np.array([]), np.array([])

    def get_range_azimuth_heatmap(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get the range-azimuth heatmap with proper scaling and axes.
        
        Returns:
            Tuple containing:
            - 2D numpy array of heatmap values in dB
            - 1D numpy array of range values in meters
            - 1D numpy array of azimuth values in degrees
        """
        # Safety check for azimuth_heatmap attribute
        if not hasattr(self, 'azimuth_heatmap') or self.azimuth_heatmap is None:
            return np.array([]), np.array([]), np.array([])
        
        # Check if azimuth_heatmap is empty or has invalid shape
        if len(self.azimuth_heatmap) == 0 or self.azimuth_heatmap.shape[0] == 0:
            return np.array([]), np.array([]), np.array([])
            
        # Get radar parameters - use actual calculated values from config
        num_range_bins = self.config_params.get('rangeBins', 256)
        range_resolution = self.config_params.get('rangeStep')
        
        if range_resolution is None:
            logger.warning("rangeStep not found in config_params, using default 0.044 m/bin")
            range_resolution = 0.044  # Default from profile
        
        # The azimuth heatmap is range_bins × num_virtual_antennas
        if len(self.azimuth_heatmap.shape) < 2:
            logger.warning("azimuth_heatmap is not 2D, returning empty arrays")
            return np.array([]), np.array([]), np.array([])
            
        num_virtual_antennas = self.azimuth_heatmap.shape[1]
        
        # Create range axis using actual range resolution
        range_axis = np.arange(num_range_bins) * range_resolution  # Start from 0
        
        # Convert heatmap values to dB (assuming they are linear magnitude)
        # Handle zeros properly to avoid log(0) warnings
        heatmap_linear = self.azimuth_heatmap.astype(np.float32)
        # Replace zeros with a small positive value to avoid log(0)
        heatmap_linear[heatmap_linear == 0] = 1e-10
        heatmap_db = 20 * np.log10(heatmap_linear)
        
        # Interpolate azimuth axis for smoother display
        # Original azimuth axis covers ±90 degrees with num_virtual_antennas points
        original_azimuth_axis = np.linspace(-90, 90, num_virtual_antennas)  # degrees
        
        # Create interpolated azimuth axis with more points for smoother display
        interpolated_azimuth_points = 64  # Increase from 8 to 64 points
        interpolated_azimuth_axis = np.linspace(-90, 90, interpolated_azimuth_points)  # degrees
        
        # Interpolate the heatmap along the azimuth axis using RegularGridInterpolator
        from scipy.interpolate import RegularGridInterpolator
        
        # Create interpolation function
        # RegularGridInterpolator expects (y, x) coordinates for the grid
        # where y = range, x = azimuth
        interp_func = RegularGridInterpolator((range_axis, original_azimuth_axis), heatmap_db, method='linear')
        
        # Create meshgrid for interpolation
        range_mesh, azimuth_mesh = np.meshgrid(range_axis, interpolated_azimuth_axis, indexing='ij')
        points = np.column_stack((range_mesh.ravel(), azimuth_mesh.ravel()))
        
        # Interpolate to new azimuth axis
        interpolated_heatmap = interp_func(points).reshape(heatmap_db.shape[0], interpolated_azimuth_points)
        
        return interpolated_heatmap, range_axis, interpolated_azimuth_axis

    def get_noise_profile(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get noise profile data in dB scale.
        
        Returns:
            Tuple of (range_bins, noise_profile_dB) where:
            - range_bins: Array of range bin indices
            - noise_profile_dB: Noise profile in dB scale
        """
        if self.noise_profile is None:
            return np.array([]), np.array([])
        
        # Convert to dB scale (similar to range profile)
        noise_dB = 20 * np.log10(self.noise_profile.astype(np.float32) + 1e-10)
        range_bins = np.arange(len(noise_dB))
        
        return range_bins, noise_dB
    
    def get_complex_range_profile(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Get complex range profile data.
        
        The complex data represents the raw radar signal at the 0th Doppler bin 
        (stationary objects) for each range bin, stored as complex numbers.
        
        Returns:
            Tuple of (range_bins, magnitude, phase) where:
            - range_bins: Array of range bin indices
            - magnitude: Magnitude of complex range profile in dB
            - phase: Phase of complex range profile in radians
        """
        if self.adc_complex is None or len(self.adc_complex) == 0:
            return np.array([]), np.array([]), np.array([])
        
        # The adc_complex is already stored as complex numbers from parsing
        # Calculate magnitude and phase directly
        magnitude = np.abs(self.adc_complex)
        phase = np.angle(self.adc_complex)
        
        # Convert magnitude to dB scale
        magnitude_dB = 20 * np.log10(magnitude + 1e-10)
        
        # Create range bins array
        range_bins = np.arange(len(magnitude_dB))
        
        return range_bins, magnitude_dB, phase


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
        
    def __next__(self) -> 'RadarData':
        """
        Get the next radar frame as a RadarData object.
        
        Returns:
            RadarData: Radar data object for the next frame
            
        Raises:
            StopIteration: If the radar connection is closed or not running
        """
        if (self.radar_connection is None or 
            not self.radar_connection.is_connected() or 
            not self.radar_connection.is_running):
            raise StopIteration
            
        try:
            # Create a new RadarData object with the next frame
            base_class_name = self.__class__.__qualname__.replace('Iterator', '')
            radar_data_class = globals().get(base_class_name)

            if radar_data_class is None:
                logging.error(f"Could not find RadarData class: {base_class_name}")
                raise StopIteration("Internal error: RadarData class not found.")

            radar_data_obj = radar_data_class(
                self.radar_connection,
                config_params=self.radar_connection.radar_params
            )
            
            return radar_data_obj
        except Exception as e:
            logging.error(f"Error reading next radar frame: {e}")
            raise StopIteration

