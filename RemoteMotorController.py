#!/usr/bin/env python
import logging as log
import sys
import time
import websockets
import asyncio
import json
import config
from remote import Remote, LogSeverity, LogType


class RemoteMotorController:
    def __init__(self, robot_controller, address="localhost"):
        # log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        self.robot_controller = robot_controller
        self.address_nr = address
        self.ws_receiver = None
        self.ws_sender = None
        self.message = None
        self.front_sensor_value = None
        self.back_sensor_value = None
        self.remote = self.robot_controller.remote
        self.ev3_turning_constant = None

    def connect(self, port_nr=8866, sender=True):
        if sender:
            est_server = websockets.serve(self.setup_sender, port=port_nr, ping_interval=None)
        else:
            est_server = websockets.serve(self.setup_receiver, port=19221, ping_interval=None)
        try:
            log.info("Waiting for EV3 to connect on port {}...".format(port_nr))
            asyncio.get_event_loop().run_until_complete(est_server)
        finally:
            pass

    @asyncio.coroutine
    def setup_sender(self, websocket, path):
        log.info("Web socket connection established on {}:{}".format(websocket.host, websocket.port))
        self.ws_receiver = websocket
        while True:
            if self.message is not None:
                log.info("[Pi > EV3] Sending message \"{}\"".format(self.message))
                yield from self.ws_receiver.send(self.message)
                self.message = None
            pass

    @asyncio.coroutine
    def setup_receiver(self, websocket, path):
        log.info("Web socket connection established on {}:{}".format(websocket.host, websocket.port))
        self.ws_sender = websocket
        while True:
            msg = yield from self.ws_sender.recv()
            self.process_message(msg)


    def process_message(self, msg):
        package = json.loads(msg)
        valid_message = True
        if package["type"] == "sensor":
            log.info("[Pi < EV3] front_sensor: {}, back_sensor: {}".format(package["front_sensor"], package["back_sensor"]))

            if self.front_sensor_value is None:
                self.front_sensor_value = [2550, 2550, 2550, 2550]
            if self.back_sensor_value is None:
                self.back_sensor_value = [2550, 2550, 2550, 2550]

            self.front_sensor_value = self.front_sensor_value[1:]
            self.back_sensor_value = self.back_sensor_value[1:]

            self.front_sensor_value.append(int(package["front_sensor"]))
            self.back_sensor_value.append((package["back_sensor"]))
        elif package["type"] == "init":
            log.info("[Pi < EV3] Received init messages: {}".format(str(package)))
            self.ev3_turning_constant = package["turning_constant"]
        elif package["type"] == "distress":
            log.info("[Pi < EV3] Distress signal received, reason: {}".format(package["message"]))
        elif package["type"] == "error":
            log.error("[Pi < EV3] Error message received, reason: {}".format(package["message"]))
            sys.exit(1)
        elif package["type"] == "approach_complete":
            log.error("[Pi < EV3] Approach completed.")
            if package["approach_problem"]:
                self.robot_controller.approach_complete = True
                self.robot_controller.retrying_approach = True
            else:
                self.robot_controller.watered = package["watered"]
                self.robot_controller.on_approach_complete()
        elif package["type"] == "retry_complete":
            log.error("[Pi < EV3] Retry completed.")
            self.robot_controller.on_retry_complete()
        elif package["type"] == "approach_escape_complete":
            log.error("[Pi < EV3] Retry completed.")
            self.robot_controller.on_approach_escape_complete()
        else:
            log.warning("[Pi < EV3] Message received not recognisable")
            valid_message = False
        if valid_message:
            msg_send = ""
            if "message" in package:
                msg_send = package["message"]
            if package["type"] != "sensor":
                current_plant_id = None
                if self.robot_controller.current_qr_approached is not None:
                    try:
                        current_plant_id = int(self.robot_controller.current_qr_approached[5:])
                    except:
                        pass
                self.remote.create_log_entry(LogType.UNKNOWN, package["type"] + ": " + msg_send, severity=LogSeverity(package["severity"]), plant_id=current_plant_id)

    def generate_action_package(self, msg):
        out = {
            "action": msg
        }
        return out

    def retry_approach(self):
        package = self.generate_action_package("retry_approach")
        self.message = json.dumps(package)
        self.robot_controller.retrying_approach = True
        time.sleep(1)

    def turn_right(self, deg):
        # log.info("Turning right.")
        package = self.generate_action_package("right")
        package["angle"] = deg
        package["turn_timed"] = False
        self.message = json.dumps(package)
        time.sleep(1)

    def turn_right_timed(self, time):
        # log.info("Executing timed right turn.")
        package = self.generate_action_package("right")
        package["turn_timed"] = True
        package["turn_turnTime"] = time
        self.message = json.dumps(package)
        time.sleep(1)

    def turn_left(self, deg):
        # log.info("Turning left.")
        package = self.generate_action_package("left")
        package["angle"] = deg
        package["turn_timed"] = False
        self.message = json.dumps(package)
        time.sleep(1)

    def turn_left_timed(self, time):
        # log.info("Executing timed left turn.")
        package = self.generate_action_package("left")
        package["turn_timed"] = True
        package["turn_turnTime"] = time
        self.message = json.dumps(package)
        time.sleep(1)

    def go_forward(self, forward_time=-1):
        # log.info("Going forward.")
        package = self.generate_action_package("forward")
        package["time"] = forward_time
        self.message = json.dumps(package)
        time.sleep(1)

    def go_backward(self, backup_time=-1):
        # log.info("Going backward.")
        package = self.generate_action_package("backward")
        package["time"] = backup_time
        self.message = json.dumps(package)
        time.sleep(1)

    def random_walk(self):
        # log.info("Performing random walk.")
        package = self.generate_action_package("random")
        self.message = json.dumps(package)
        time.sleep(1)

    def stop(self):
        # log.info("Stopping.")
        package = self.generate_action_package("stop")
        self.message = json.dumps(package)
        time.sleep(1)

    def approached(self, raise_arm=True):
        # log.info("Plant approached.")
        package = self.generate_action_package("approached")
        package["raise_arm"] = raise_arm
        self.message = json.dumps(package)
        time.sleep(1)

    def approach_escape(self):
        package = self.generate_action_package("approach_escape")
        self.message = json.dumps(package)
        time.sleep(1)

    def random(self):
        # log.info("Triggering random walk.")
        package = self.generate_action_package("random")
        self.message = json.dumps(package)
        time.sleep(1)

    def arm_up(self):
        package = self.generate_action_package("arm_up")
        self.message = json.dumps(package)
        time.sleep(1)

    def arm_down(self):
        package = self.generate_action_package("arm_down")
        self.message = json.dumps(package)
        time.sleep(1)