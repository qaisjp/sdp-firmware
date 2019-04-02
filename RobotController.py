#!/usr/bin/env python
from Vision_SSD300 import Vision
from Navigator import Navigator
from QRReader import QRReader
import threading
import logging as log
import sys
from scheduler import Scheduler, Event
from remote import Remote, RPCType
import config
import asyncio
import os
import time
import base64
import cv2


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

        self.received_frame = None
        self.qr_reader = QRReader()
        self.last_qr_approached = None
        self.current_qr_approached = None
        self.approach_complete = True
        self.retrying_approach = False
        self.standby_mode = True

        if config.RESPOND_TO_API:
            host = config.API_HOST
            if config.API_SECURE:
                host = "wss://"+host
            else:
                host = "ws://"+host

            self.remote = Remote(config.UUID, host)
            self.remote.add_callback(
                RPCType.MOVE_IN_DIRECTION, self.remote_move)
            self.remote.add_callback(
                RPCType.EVENTS, self.on_events_received)

            rm_thread = threading.Thread(target=self.thread_remote,
                                         daemon=True)
            rm_thread.start()
            # rm_thread.join()

        # Create the navigation system
        self.navigator = Navigator(self, verbose=True)

        threading.Thread(target=self.vision.start).start()

    def remote_move(self, direction):
        self.navigator.remote_move(direction)

    def thread_remote(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # self.sched = Scheduler()
        loop.run_until_complete(self.remote.connect())

    def process_visual_data(self, predictions, frame):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """
        if not self.standby_mode:
            self.received_frame = frame
            self.navigator.on_new_frame(predictions)
        else:
            # Stop immediately? Wait until the jobs to finish to stop?
            if not self.approach_complete:
                pass
            elif self.retrying_approach:
                pass
            else:
                # Any other switches to flip?
                # Reset read QR codes
                self.current_qr_approached = None
                self.last_qr_approached = None
                # Stop the motor
                self.navigator.remote_motor_controller.stop()

    def read_qr_code(self):
        # Read the QR code
        tries = 3
        qr_codes = self.qr_reader.identify(self.received_frame)
        while tries > 0:
            if len(qr_codes) == 0:
                log.warning("No plant QR found.")
                tries -= 1
            else:
                for qr in qr_codes:
                    self.current_qr_approached = qr
                    log.info("Plant QR found: {}".format(qr))
                break

    def on_plant_found(self):
        # Send message to initiate approach command, until instructed to continue
        if self.current_qr_approached is None:
            log.warning("No QR found, retrying approach")
            self.retrying_approach = True
            self.navigator.remote_motor_controller.retry_approach()
        else:
            # if past == current, do something here
            self.approach_complete = False
            self.navigator.remote_motor_controller.approached()

    def on_approach_complete(self):
        # Take a picture here

        if self.current_qr_approached is not None:
            if self.current_qr_approached.startswith("gbpl:"):
                self.remote.plant_capture_photo(int(self.current_qr_approached[5:]), base64.b64encode(cv2.imencode(".jpg", self.received_frame)[1]).decode("utf-8"))
        else:
            log.warning("[Pi] No QR code found during this approach, photo will not be sent.")

        self.last_qr_approached = self.current_qr_approached
        self.current_qr_approached = None
        self.navigator.remote_motor_controller.approach_escape()

    def on_approach_escape_complete(self):
        self.navigator.random_search_mode = True # Flip on the random search
        self.navigator.remote_motor_controller.random_walk()

        self.approach_complete = True

    def on_retry_complete(self):
        self.retrying_approach = False

    def on_plant_seen(self):
        pass

    def on_events_received(self, data):
        # self.sched.push_events(list(map(Event.from_dict, data)))
        pass

    def on_leaving_standby(self):
        # Start random search
        self.navigator.random_search_mode = True
        self.navigator.remote_motor_controller.random_walk()

        # Turn off standby mode
        self.standby_mode = False

    def on_entering_standby(self):
        self.standby_mode = True

def main():
    if os.getenv("http_proxy") is not None:
        print("You are a monster.")
        print("Use start.sh. Do not run this Python file yourself.")
        return

    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
