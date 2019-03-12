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
            if self.message != None:
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
        log.info("[Pi < EV3] front_sensor: {}, back_sensor: {}".format(package["front_sensor"], package["back_sensor"]))
        pass
        

    def turn_right(self):
        #log.info("Turning right.")
        self.message = "right"
        time.sleep(1)

    def turn_left(self):
        #log.info("Turning left.")
        self.message = "left"
        time.sleep(1)

    def go_forward(self):
        #log.info("Going forward.")
        self.message = "forward"
        time.sleep(1)

    def go_backward(self):
        #log.info("Going backward.")
        self.message = "backward"
        time.sleep(1)

    def random_walk(self):
        #log.info("Performing random walk.")
        self.message = "random"
        time.sleep(1)

    def stop(self):
        #log.info("Stopping.")
        self.message = "stop"
        time.sleep(1)

def main():
    rc = RemoteMotorController()
    try:
        rc.connect()
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        log.info("Stopping server...")
        asyncio.get_event_loop().close()

if __name__ == "__main__":
    main()
