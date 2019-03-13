#!/usr/bin/env python3
from picamera import PiCamera
from pyzbar.pyzbar import decode
from time import sleep
import cv2
import imutils
from imutils.video import VideoStream
import logging as log
import sys

class QRReader:
    def __init__(self):
        self.camera = PiCamera()
        self.camera.resolution = (1024, 768)
        self.found_id = None

    def snapshot_and_identify(self):
        try:
            # Take a picture using PiCamera
            output_location = "dummy.jpg"
            self.camera.capture(output_location)

            # Read the saved picture into PIL frame
            frame = cv2.imread(output_location)
            decoded = decode(frame)
            for qr in decoded:
                # Update the QR code that this object holds, if any
                self.found_id = qr.data
        finally:
            pass

# QR capture, using PiCamera library.
def main():
    sleep(2) # Camera warm-up

if __name__ == "__main__":
    main()
