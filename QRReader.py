#!/usr/bin/env python3
from picamera import PiCamera
from pyzbar.pyzbar import decode
from time import sleep
import cv2
import imutils
import logging as log
import sys

class QRReader:
    def __init__(self):
        self.found_id = None

    def identify(self, frame):
        try:
            # Read the saved picture into PIL frame
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
