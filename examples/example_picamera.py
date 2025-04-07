from xwr68xxisk.cameras import RaspberryPiCamera
import cv2

camera = RaspberryPiCamera()
camera.config = {
    'width': 1280,
    'height': 720,
    'fps': 30,
    'exposure': 20000,  # 20ms exposure time
    'gain': 2.0        # Analog gain value
}

camera.start()
try:
    for frame_data in camera:
        image = frame_data['image']
        # Process frame as needed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
finally:
    camera.stop()
