#!/usr/bin/env python
from Vision_SSD300 import Vision
from Navigator import Navigator
import threading
import logging as log
import sys
from QRReader import QRReader


class RobotController:
    model_xml = '/home/student/ssd300.xml'
    model_bin = '/home/student/ssd300.bin'

    def __init__(self):
        self.vision = Vision(
                        RobotController.model_xml,
                        RobotController.model_bin,
                        self,
                        is_headless=False,
                        live_stream=False,
                        confidence_interval=0.5)

        self.navigator = Navigator(self, verbose=True)
        self.qr_reader = QRReader()

        threading.Thread(target=self.vision.start).start()
        threading.Thread(target=self.navigator.start).start()

    def process_visual_data(self, predictions):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """
        self.navigator.navigate(predictions)
        if self.navigator.escape_mode:
            # Identify QR code
            self.qr_reader.snapshot_and_identify()
            log.info(self.qr_reader.found_id)
            



def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
