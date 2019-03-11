#!/usr/bin/env python3
from picamera import PiCamera
from pyzbar.pyzbar import decode
from time import sleep
import cv2
import imutils
from imutils.video import VideoStream
import logging as log
import sys

# QR capture, using PiCamera library.
def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout) # Log level
    camera = PiCamera()
    camera.resolution = (1024, 768)

    sleep(2) # Camera warm-up
    for i in range(1000):
        try:
            # Take a picture using PiCamera
            log.info("")
            output_location = "dummy.jpg"
            camera.capture(output_location)

            # Read the saved picture into PIL frame
            frame = cv2.imread(output_location)
            decoded = decode(frame)
            print("Pyzbar data {} = {}".format(i, decoded))

            # sleep(1) # Interval between frames
        finally:
            pass

if __name__ == "__main__":
    main()
