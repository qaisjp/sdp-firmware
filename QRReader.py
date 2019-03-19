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
            qr_codes = set()
            for qr in decoded:
                qr_string = qr.data.decode("utf-8")
                # Update the QR code that this object holds, if any
                if not qr_string.startswith("growbot:plant:"):
                    log.info("QR code not valid")
                else:
                    qr_codes.add(qr_string)
            return qr_codes
        finally:
            pass


# QR capture, using PiCamera library.
def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    sleep(2) # Camera warm-up

if __name__ == "__main__":
    main()
