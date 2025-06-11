import time
from picamera2 import Picamera2, Preview
from picamera2.encoders import H264Encoder

picam = Picamera2()
video_config = picam.create_video_configuration()
picam.configure(video_config)
encoder = H264Encoder(10000000)

picam.start_preview(Preview.QT)
picam.start_recording(encoder, 'test-recode.h264')
time.sleep(10)
picam.stop_recording()