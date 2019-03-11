#!/usr/bin/env python3
from picamera import PiCamera
from picamera.array import PiRGBArray
from pyzbar.pyzbar import decode
from PIL import Image
from time import sleep
import cv2
import imutils
from imutils.video import VideoStream

# QR capture, using VideoStream. Outputs video with cv2.imshow().
def main():
    vs = VideoStream(usePiCamera=True, resolution=(640, 320)).start()
    sleep(2) # Camera warm-up
    for i in range(1000):
        try:
            frame = vs.read() # Read a frame from VideoStream
            decoded = decode(frame)
            print("Pyzbar i = {}, found {}".format(i, len(decoded)))

            # Show image. Can be modified to export results
            cv2.imshow("Image", frame)
            cv2.waitKey(1)
        finally:
            # Close the stream?
            pass

if __name__ == "__main__":
    main()
