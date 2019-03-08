#!/usr/bin/env python
import logging as log
import sys
import time
from remote import Remote
import websockets
import asyncio


class RemoteMotorController:
    def __init__(self, address="localhost", port=8866):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        self.address_nr = address
        self.port_nr = port
        self.est_server = websockets.serve(self.setup, self.address_nr, self.port_nr)
        try:
            asyncio.get_event_loop().run_until_complete(self.est_server)
            log.info("Info")
        finally:
            pass


    @asyncio.coroutine
    def setup(self, websocket, path):
        msg = yield from websocket.recv()
        print(msg)
        if msg == "conn-est":
            log.info("Web socket connection established on {}:{}".format(websocket.host, websocket.port))

    def turn_right(self):
        log.info("Turning right.")
        time.sleep(1)

    def turn_left(self):
        log.info("Turning left.")
        time.sleep(1)

    def go_forward(self):
        log.info("Going forward.")
        time.sleep(1)

    def go_backward(self):
        log.info("Going backward.")
        time.sleep(1)

    def random_walk(self):
        log.info("Performing random walk.")
        time.sleep(1)

    def stop(self):
        log.info("Stopping.")
        time.sleep(1)

def main():
    rc = RemoteMotorController()
    log.info("Hohoho")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        log.info("Stopping server...")
        asyncio.get_event_loop().close()

if __name__ == "__main__":
    main()
