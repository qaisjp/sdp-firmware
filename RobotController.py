#!/usr/bin/env python
from Vision_SSD300 import Vision
from Navigator import Navigator
import time
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
                        is_headless=True,
                        live_stream=False,
                        confidence_interval=0.5)

        self.navigator = Navigator(self, verbose=True)

        time.sleep(10)
        # self.qr_reader = QRReader()

        threading.Thread(target=self.vision.start).start()

    def process_visual_data(self, predictions):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """

        self.navigator.on_new_frame(predictions)

    def on_plant_found(self):
        pass

    def remote_move(self, direction):
        print("Start: moving in direction {}".format(direction))
        if direction == "forward":
            self.drive_forward()
        elif direction == "backward":
            self.drive_backward()
        elif direction == "left":
            self.left_side_turn()
        elif direction == "right":
            self.right_side_turn()
        elif direction == "brake":
            self.stop()
        elif direction == "armup":
            self.raise_arm()
        elif direction == "armdown":
            self.lower_arm()
        else:
            print("Unknown direction received")
        print("End: moving in direction {}".format(direction))


def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
