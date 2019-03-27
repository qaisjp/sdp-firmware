#!/usr/bin/env python
import logging as log
import sys
import time
import websockets
import asyncio
import json


class RemoteMotorController:
    def __init__(self, address="localhost"):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        self.address_nr = address
        self.ws_receiver = None
        self.ws_sender = None
        self.message = None

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
        if package["message"] == "sensor":
            log.info("[Pi < EV3] front_sensor: {}, back_sensor: {}".format(package["front_sensor"], package["back_sensor"]))
        elif package["message"] == "distress":
            log.info("[Pi < EV3] Distress signal received, reason:{}".format(package["reason"]))

    def generate_action_package(self, msg):
        out = {
            "action": msg
        }
        return out

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

    def go_forward(self):
        # log.info("Going forward.")
        package = self.generate_action_package("forward")
        self.message = json.dumps(package)
        time.sleep(1)

    def go_backward(self):
        # log.info("Going backward.")
        package = self.generate_action_package("backward")
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

    def random(self):
        # log.info("Triggering random walk.")
        package = self.generate_action_package("random")
        self.message = json.dumps(package)
        time.sleep(1)