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
from serial_io import SerialIO
import json

class RobotController:
    model_xml = '/home/student/ssd300.xml'
    model_bin = '/home/student/ssd300.bin'

    def __init__(self):
        self.vision = Vision(
                        RobotController.model_xml,
                        RobotController.model_bin,
                        self,
                        is_headless=True,
                        live_stream=True,
                        confidence_interval=0.5)

        self.received_frame = None
        self.qr_reader = QRReader()
        self.last_qr_approached = None
        self.current_qr_approached = None
        self.approach_complete = True
        self.retrying_approach = False
        self.standby_mode = True
        self.standby_invoked = True
        self.serial_io = SerialIO('/dev/ttyACM0', 115200, self)
        self.actions = {}
        self.watered = False

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
            self.remote.add_callback(
                RPCType.SET_STANDBY, self.set_standby)

            rm_thread = threading.Thread(target=self.thread_remote,
                                         name="remote", daemon=True)
            rm_thread.start()
            # rm_thread.join()

        # Create the navigation system
        self.navigator = Navigator(self, verbose=True)

        threading.Thread(target=self.vision.start, name="vision").start()

    def remote_move(self, direction):
        self.navigator.remote_move(direction)

    def run_event(self, event):
        if self.standby_mode and len(self.actions.keys()) == 0:
            self.set_standby(False, justMove=True)
        for action in event.actions:
            pid = action["plant_id"]
            if pid not in self.actions:
                self.actions[pid] = []

            self.actions[pid].append(action["name"])

    def thread_remote(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.sched = Scheduler()
        self.sched.run_event_cb = self.run_event
        loop.run_until_complete(self.remote.connect())

    def enabled(self):
        return len(self.actions) > 0 or not self.standby_mode

    def clean_actions(self):
        new_actions = {}
        for key in self.actions:
            if self.actions[key] != []:
                new_actions[key] = self.actions[key]

        self.actions = new_actions

    def process_visual_data(self, predictions, frame):
        """
        Forwards messages to navigator instance.
        :param predictions:     List of predictions produced by the VPU
        :return:
        """
        # If the standby is currently undergoing, but standby mode is False, stop standby mode here
        if self.standby_invoked and not self.standby_mode:
            self.standby_invoked = False
            self.random_search_mode = True
            self.navigator.remote_motor_controller.random()
            self.standby_invoked = False

        # If the sensor's last read time is long enough (1 hour), attempt to read the sensor
        if time.time() - self.serial_io.sensor_last_read > 3600 and not self.serial_io.value_reading:
            threading.Thread(name="serial_read", target=self.serial_io.read_value).start()

        if self.enabled():
            log.info("self.actions: {}, standby_mode: {}".format(self.actions, self.standby_mode))
            self.clean_actions()
            self.received_frame = frame
            self.navigator.on_new_frame(predictions)
        else:
            if self.standby_mode:
                log.info("\033[0;34m[Pi] Standby mode flag detected")
                if not self.approach_complete:
                    log.info("\033[1;37;44m[Pi] Robot approaching, ignoring flag")
                elif self.retrying_approach:
                    log.info("\033[1;37;44m[Pi] Robot retrying approach, ignoring flag")
                else:
                    if not self.standby_invoked:
                        self.navigator.remote_motor_controller.stop()
                        log.info("\033[1;37;44m[Pi] Invoking standby mode")
                        # Any other switches to flip?
                        # Reset read QR codes
                        self.current_qr_approached = None
                        self.last_qr_approached = None
                        # Stop the motor
                        self.standby_invoked = True
            elif len(self.actions) == 0:
                log.info("\033[0;34m[Pi] Robot has no event left to complete")
            # Stop immediately? Wait until the jobs to finish to stop?


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
        elif self.current_qr_approached.startswith("gbpl:"):
            # Parse the QR
            plant_id = int(self.current_qr_approached[5:])
            if not self.standby_invoked:
                # If robot is not in standby mode, go forward anyways
                self.approach_complete = False
                self.navigator.remote_motor_controller.approached()
            elif plant_id in self.actions:
                if len(self.actions[plant_id]) == 0:
                    log.info("Plant {} has no task left to complete, leaving...".format(str(plant_id)))
                    self.last_qr_approached = self.current_qr_approached
                    self.current_qr_approached = None
                    self.navigator.remote_motor_controller.approach_escape()
                else:
                    self.approach_complete = False
                    if "PLANT_WATER" in self.actions[plant_id] or not self.standby_invoked:
                        self.navigator.remote_motor_controller.approached()
                    else:
                        self.navigator.remote_motor_controller.approached(raise_arm=False)
            else:
                log.info("Plant {} has no task assigned, leaving...".format(str(plant_id)))
                self.last_qr_approached = self.current_qr_approached
                self.current_qr_approached = None
                self.navigator.remote_motor_controller.approach_escape()
        else:
            log.warning("Invalid QR code {}".format(self.current_qr_approached))
            self.last_qr_approached = self.current_qr_approached
            self.current_qr_approached = None
            self.navigator.remote_motor_controller.approach_escape()

    def on_approach_complete(self):
        # Take a picture here
        plant_id = None


        if self.current_qr_approached is not None:
            if self.current_qr_approached.startswith("gbpl:"):
                plant_id = int(self.current_qr_approached[5:])
                if "PLANT_CAPTURE_PHOTO" in self.actions.get(plant_id, []) or not self.standby_invoked:
                    self.remote.plant_capture_photo(int(self.current_qr_approached[5:]), base64.b64encode(cv2.imencode(".jpg", self.received_frame)[1]).decode("utf-8"))
        else:
            log.warning("[Pi] No QR code found during this approach, photo will not be sent.")

        self.last_qr_approached = self.current_qr_approached
        self.current_qr_approached = None
        try:
            if plant_id is not None:
                if self.watered:
                    self.actions[plant_id].remove("PLANT_WATER")
                self.watered = False
                if self.actions[plant_id] == []:
                    self.actions.pop(plant_id, None)
                self.actions[plant_id].remove("PLANT_CAPTURE_PHOTO")
        except:
            pass
        finally:
            self.navigator.remote_motor_controller.approach_escape()

    def on_approach_escape_complete(self):
        self.navigator.random_search_mode = True # Flip on the random search
        self.navigator.remote_motor_controller.random_walk()
        self.clean_actions()
        self.approach_complete = True

    def on_retry_complete(self):
        self.retrying_approach = False
        self.navigator.approach_frame_counter = 8

    def on_plant_seen(self):
        pass

    def on_events_received(self, data):
        events = list(map(Event.from_dict, data))
        non_ephemeral = []

        for e in events:
            if e.ephemeral:
                self.run_event(e)
            else:
                non_ephemeral.append(e)

        self.sched.push_events(non_ephemeral)
        pass

    def set_standby(self, mode, justMove=False):
        if mode:
            self.standby_mode = True
            while not hasattr(self, "navigator"):
                pass
            self.navigator.remote_motor_controller.stop()
            return

        while not hasattr(self, "navigator"):
            pass

        # Start random search
        self.navigator.random_search_mode = True
        self.navigator.remote_motor_controller.random_walk()

        if not justMove:
            # Turn off standby mode
            self.standby_mode = False

    def get_state(self):
        if self.standby_mode:
            return "Standby Mode"
        elif self.retrying_approach:
            return "Retrying approach"
        elif self.navigator.get_random_search_mode():
            return "Random Search Mode"
        elif self.navigator.get_follow_mode():
            return "Follow Mode"
        elif self.navigator.get_escape_mode():
            return "Escape Mode"

def main():
    if os.getenv("http_proxy") is not None:
        print("You are a monster.")
        print("Use start.sh. Do not run this Python file yourself.")
        return

    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s\033[0m", level=log.DEBUG, stream=sys.stdout)
    RobotController()


if __name__ == "__main__":
    main()
