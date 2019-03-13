#!/usr/bin/env python
from Vision_SSD300 import Vision
from Navigator import Navigator
import threading
import logging as log
import sys
from scheduler import Scheduler
from remote import Remote, RPCType
import config
import asyncio


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
        self.sched = Scheduler()
        # self.qr_reader = QRReader()

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

            threading.Thread(target=self.thread_remote, daemon=True).start()

        threading.Thread(target=self.vision.start).start()

    def thread_remote(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.remote.connect())

    def process_visual_data(self, predictions):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """

        self.navigator.on_new_frame(predictions)

    def on_plant_found(self):
        pass

    def on_events_received(self, data):
        print(data)

    def remote_move(self, direction):
        if direction == "forward":
            print("drive forward")
        elif direction == "backward":
            print('drive backward')
        elif direction == "left":
            print('left turn')
        elif direction == "right":
            print('right turn')
        elif direction == "brake":
            print('brake')
        elif direction == "armup":
            print('armup')
        elif direction == "armdown":
            print('armdown')
        else:
            print("Unknown direction received")


def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
