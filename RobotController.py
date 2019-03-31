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
        self.received_frame = None
        self.qr_reader = QRReader()
        self.last_qr_approached = None
        self.current_qr_approached = None
        self.approach_complete = True
        self.retrying_approach = False

        if config.RESPOND_TO_API:
            host = config.API_HOST
            if config.API_SECURE:
                host = "wss://"+host
            else:
                host = "ws://"+host

            self.remote = Remote(config.UUID, host)
            self.remote.add_callback(
                RPCType.MOVE_IN_DIRECTION, self.navigator.remote_move)
            self.remote.add_callback(
                RPCType.EVENTS, self.on_events_received)

            rm_thread = threading.Thread(target=self.thread_remote, daemon=True)
            rm_thread.start()
            # rm_thread.join()

        threading.Thread(target=self.vision.start).start()

    def thread_remote(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.sched = Scheduler()
        loop.run_until_complete(self.remote.connect())

    def process_visual_data(self, predictions, frame):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """

        self.received_frame = frame
        self.navigator.on_new_frame(predictions)

    def read_qr_code(self):
        # Read the QR code
        tries = 3
        qr_codes = self.qr_reader.identify(self.received_frame)
        while tries > 0:
            if len(qr_codes) == 0:
                log.warning("No plant QR found.")
                self.current_qr_approached = None
                tries -= 1
            else:
                for qr in qr_codes:
                    self.current_qr_approached = qr
                    log.info("Plant QR found: {}".format(qr))
                break

    def on_plant_found(self):
        # Take a picture here
        # Approach again?
        # Send message to initiate approach command, until instructed to continue
        self.approach_complete = False
        self.navigator.remote_motor_controller.approached()
        # while not self.navigator.remote_motor_controller.approach_complete:
        #     pass

    def on_approach_complete(self):
        self.approach_complete = True
        self.last_qr_approached = self.current_qr_approached

    def on_retry_complete(self):
        self.retrying_approach = False

    def on_plant_seen(self):
        pass

    def on_events_received(self, data):
        self.sched.push_events(list(map(Event.from_dict, data)))
        pass


def main():
    if os.getenv("http_proxy") is not None:
        print("You are a monster.")
        print("Use start.sh. Do not run this Python file yourself.")
        return

    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
