"""IMU BNO086

UART-RVC interface to the BNO086 IMU. 

The BNO086 is a 9-axis absolute orientation sensor with triaxial accelerometer, gyroscope,
and magnetometer. It provides real-time 3D orientation, heading, calibrated acceleration
and angular velocity at 100 Hz update rate.

Message Format (19 bytes):
- Header (2 bytes): 0xAAAA
- Index (1 byte): Monotonically increasing count (0-255)
- Yaw (2 bytes): ±180° in 0.01° increments (Z-axis rotation)
- Pitch (2 bytes): ±90° in 0.01° increments (Y-axis rotation)
- Roll (2 bytes): ±180° in 0.01° increments (X-axis rotation)
- X/Y/Z acceleration (2 bytes each): in mg units
- Motion Intent (1 byte): BNO086 specific
- Motion Request (1 byte): BNO086 specific
- Reserved (1 byte): Set to zero
- Checksum (1 byte): Sum of bytes 2-18

Example message: 0xAA AA DE 01 00 92 FF 25 08 8D FE EC FF D1 03 00 00 00 E7
Decoded values:
- Index = 222 (0xDE)
- Yaw = 0.01° (0x0001)
- Pitch = -1.10° (0xFF92)
- Roll = 20.85° (0x0825)
- X-accel = -371 mg (0xFE8D)
- Y-accel = -20 mg (0xFFEC)
- Z-accel = 977 mg (0x03D1)
- Checksum = 0xE7

Note: Rotations should be applied in order: yaw, pitch, then roll.


"""

import serial
import struct
import threading
import time


class IMU:
    """BNO086 IMU interface that provides continuous reading of sensor data via UART.
    
    The class creates a background thread that reads data at 100Hz and provides access
    to the latest readings through an iterator interface.
    
    Returns data as a dictionary with keys:
    - index: packet counter
    - yaw, pitch, roll: orientation in degrees
    - x_acceleration, y_acceleration, z_acceleration: acceleration in mg
    - motion_intent, motion_request: BNO086 specific flags
    """

    def __init__(self, port):
        self.ser = serial.Serial(port, 115200)
        self.buffer = []
        self.thread = threading.Thread(target=self.read_thread)
        self.thread.start()

    def read_thread(self):
        """Continuously read IMU data in background thread."""
        while True:
            # Read exactly 19 bytes for a complete message
            data = self.ser.read(19)
            # decode the data into a dictionary
            decoded = self.decode_data(data)
            if decoded is not None:
                self.imu_dict = decoded
            time.sleep(0.01)  # 100Hz update rate

    def decode_data(self, data):
        """Decode the 19-byte IMU message.
        
        Args:
            data (bytes): 19-byte message from IMU
            
        Returns:
            dict: Dictionary containing decoded IMU values
            
        The message format is:
        - Header (2 bytes): 0xAAAA
        - Index (1 byte): 0-255 count
        - Yaw (2 bytes): ±180° in 0.01° increments 
        - Pitch (2 bytes): ±90° in 0.01° increments
        - Roll (2 bytes): ±180° in 0.01° increments
        - X acceleration (2 bytes): mg
        - Y acceleration (2 bytes): mg 
        - Z acceleration (2 bytes): mg
        - Motion Intent (1 byte)
        - Motion Request (1 byte)
        - Reserved (1 byte)
        - Checksum (1 byte)
        """
        # Check if we have a complete message
        if len(data) != 19:
            return None
            
        # Check header
        header = struct.unpack('>H', data[0:2])[0]
        if header != 0xAAAA:
            return None
            
        # Unpack all fields at once using little-endian format
        index, yaw, pitch, roll, x_accel, y_accel, z_accel, motion_intent, motion_request, reserved, checksum = \
            struct.unpack('<Bhhh hhh BB B B', data[2:])
            
        # Calculate checksum
        calc_checksum = sum(data[2:18]) & 0xFF
        if calc_checksum != checksum:
            return None
            
        # Convert angular values to degrees
        yaw = yaw / 100.0
        pitch = pitch / 100.0
        roll = roll / 100.0
            
        return {
            'index': index,
            'yaw': yaw,
            'pitch': pitch,
            'roll': roll,
            'x_acceleration': x_accel,
            'y_acceleration': y_accel,
            'z_acceleration': z_accel,
            'motion_intent': motion_intent,
            'motion_request': motion_request
        }

    def __iter__(self):
        """Return an iterator over IMU data."""
        return self

    def __next__(self):
        """Return the next IMU reading."""
        if hasattr(self, 'imu_dict'):
            return self.imu_dict
        raise StopIteration

    def read(self):
        return self.ser.read()
