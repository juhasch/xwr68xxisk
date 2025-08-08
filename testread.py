import serial
import time

#from parse import RadarData

ser = serial.Serial('/dev/ttyUSB1', 921600)

MAGIC =  b'\x02\x01\x04\x03\x06\x05\x08\x07'




#rd = RadarData()


#while True:
#    length = ser.inWaiting()#
#    if length > 0:
#        recv_data = ser.read(length)
#        print(length, recv_data[0:8])
#    time.sleep(0.1)

while True:
    data = ser.read_until(MAGIC)
    #length = len(recv_data)
    """Parse the radar data packet header."""
    version = int.from_bytes(data[0:4], byteorder='little')
    total_packet_len = int.from_bytes(data[4:8], byteorder='little')
    platform = int.from_bytes(data[8:12], byteorder='little')
    frame_number = int.from_bytes(data[12:16], byteorder='little')
    time_cpu_cycles = int.from_bytes(data[16:20], byteorder='little')
    num_detected_obj = int.from_bytes(data[20:24], byteorder='little')
    num_tlvs = int.from_bytes(data[24:28], byteorder='little')
    subframe_number = (int.from_bytes(data[28:32], byteorder='little') 
                            if num_detected_obj > 0 else None)

    print(version, total_packet_len, platform, frame_number, time_cpu_cycles, num_detected_obj, num_tlvs, subframe_number)


ser.close()

ser.close()