import websockets
import asyncio
import sys
import logging as log
import firmware

class EV3_Client:
    def __init__(self, host="10.42.0.1"):
        self.host = host
        self.est = False
        self.ws = None
        self.firmware = firmware.GrowBot(-1,-1) # Battery/water levels to be implemented
        asyncio.get_event_loop().run_until_complete(self.connect())

    @asyncio.coroutine
    def connect(self):
        self.ws = yield from websockets.connect("ws://{}:{}/".format(self.host, 8866))
        while True:
            msg = yield from self.ws.recv()
            self.message_process(msg)


    def message_process(self, msg):
        if msg == "left":
            log.info("Turning left.")
            self.firmware.left_side_turn(running_speed=100)
        elif msg == "right":
            log.info("Turning right.")
            self.firmware.right_side_turn(running_speed=100)
        elif msg == "forward":
            log.info("Going forward.")
            self.firmware.drive_forward(running_speed=100)
        elif msg == "backward":
            log.info("Going backward.")
            self.firmware.drive_backward(running_speed=100)
        elif msg == "random":
            log.info("Performing random walk.")
            # TODO: implement random walk and break conditions...
            self.firmware.drive_forward(running_speed=50)
        elif msg == "stop":
            log.info("Stopping.")
            self.firmware.stop()
        else:
            log.info("Invalid command.")

    @asyncio.coroutine
    def get_messages(self):
        msg = yield from self.ws.recv()
        log.info(msg)


def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
    ev3 = EV3_Client(host="localhost")
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    main()