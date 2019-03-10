#!/usr/bin/env python
import logging as log
import sys
import time
import websockets
import asyncio

class RemoteMotorController:
    def __init__(self, address="localhost", port=8866):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        self.address_nr = address
        self.port_nr = port
        self.ws = None
        self.message = None
        

    def connect(self):
        est_server = websockets.serve(self.setup, port=self.port_nr, ping_interval=None)
        try:
            log.info("Waiting for EV3 to connect...")
            asyncio.get_event_loop().run_until_complete(est_server)
        finally:
            pass

    @asyncio.coroutine
    def setup(self, websocket, path):
        log.info("Web socket connection established on {}:{}".format(websocket.host, websocket.port))
        self.ws = websocket
        while True:
            if self.message != None:
                yield from self.ws.send(self.message)
                self.message = None
            pass

    @asyncio.coroutine
    def send_message(self, msg):
        log.info(msg)
        if self.ws != None:
            self.ws.send(msg)

    def turn_right(self):
        log.info("Turning right.")
        self.message = "right"
        time.sleep(1)

    def turn_left(self):
        log.info("Turning left.")
        self.message = "left"
        time.sleep(1)

    def go_forward(self):
        log.info("Going forward.")
        self.message = "forward"
        time.sleep(1)

    def go_backward(self):
        log.info("Going backward.")
        self.message = "backward"
        time.sleep(1)

    def random_walk(self):
        log.info("Performing random walk.")
        self.message = "random"
        time.sleep(1)

    def stop(self):
        log.info("Stopping.")
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
