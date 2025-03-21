from xwr68xxisk.imu_recorder import IMURecorder
from xwr68xxisk.imu import IMU

# Create recorder
recorder = IMURecorder("recordings/imu_data")

# Create IMU instance
imu = IMU("/dev/ttyUSB0")

# Record some frames
for _ in range(100):
    data = next(imu)
    if data is not None:
        recorder.add_frame(data)

# Close recorder (saves data if buffering in memory)
recorder.close()
