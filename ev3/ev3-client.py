import websockets
import asyncio
import sys
import logging as log
from growbot import GrowBot
import threading
import random
import time
import json
import SigFinish


class EV3_Client:
    def __init__(self, host="pi"):
        self.host = host
        self.est = False
        self.ws_receiver = None
        self.ws_sender = None
        self.front_sensor_data = None
        self.back_sensor_data = None
        self.stop_now = False
        self.random_thread = None
        self.firmware = firmware.GrowBot(-1,-1) # Battery/water levels to be implemented
        # Battery/water levels to be implemented
        self.gb = GrowBot(-1, -1)

    def connect(self, sender=False):
        log.info("INFO")
        try:
            if not sender:
                log.info("Connecting receiver to Pi receiver...")
                asyncio.get_event_loop().run_until_complete(
                    self.setup_receiver())
            else:
                log.info("Connecting sender to Pi sender...")
                asyncio.get_event_loop().run_until_complete(
                    self.setup_sender())
        finally:
            pass

    @asyncio.coroutine
    def setup_receiver(self, port_nr=8866):
        self.ws_receiver = yield from websockets.connect(
            "ws://{}:{}/".format(self.host, port_nr), ping_interval=None)

        log.info("Web socket connection established on {}:{}".format(
            self.ws_receiver.host, self.ws_receiver.port))

        try:
            while True:
                msg = yield from self.ws_receiver.recv()
                self.message_process(msg)
        finally:
            self.gb.stop()
            self.ws_receiver.close()

    @asyncio.coroutine
    def setup_sender(self, port_nr=19221):
        self.ws_sender = yield from websockets.connect(
            "ws://{}:{}/".format(self.host, port_nr), ping_interval=None)

        log.info("Web socket connection established on {}:{}".format(
            self.ws_sender.host, self.ws_sender.port))

        try:
            while True:
                package = {
                    "front_sensor": str(self.gb.front_sensor.value()),
                    "back_sensor": str(self.gb.back_sensor.value())
                }
                log.info("[EV3 > Pi] Sending sensor data (\"front_sensor\": {}"
                         ", \"front_sensor\": {})".format(
                             package["front_sensor"], package["back_sensor"]))

                yield from self.ws_sender.send(json.dumps(package))
                self.front_sensor_data = None
                self.back_sensor_data = None
                time.sleep(5)
        finally:
            self.gb.stop()
            self.ws_sender.close()

    def message_process(self, msg):
        log.info("[EV3 < Pi] Received message \"{}\"".format(msg))
        if msg == "left":
            log.info("Turning left.")
            self.gb.left_side_turn(running_speed=100)
        elif msg == "right":
            log.info("Turning right.")
            self.gb.right_side_turn(running_speed=100)
        elif msg == "forward":
            log.info("Going forward.")
            self.gb.drive_forward(running_speed=100)
        elif msg == "backward":
            log.info("Going backward.")
            self.gb.drive_backward(running_speed=100)
        elif msg == "random":
            log.info("Performing random turn.")
            turn_left = random.random()
            degree = random.randint(60, 180)

            if turn_left < 0.5:
<<<<<<< HEAD
                self.firmware.right_side_turn(run_forever=True, running_speed=75)
            else:
                self.firmware.left_side_turn(run_forever=True, running_speed=75)

            rm_loop = asyncio.new_event_loop()
            rm_thread = threading.Thread(target=self.random_movement, args=(rm_loop,))
            self.random_thread = rm_thread
            rm_thread.setDaemon(True)
            rm_thread.start()
            
            # while rm_thread.is_alive():
            #     if self.stop_now:
            #         SigFinish.interrupt_thread(rm_thread)
            #         rm_thread.join()

        elif msg == "stop":
            log.info("Stopping.")
            self.stop_now = True
            self.firmware.stop()
        else:
            log.info("Invalid command.")

    @asyncio.coroutine
    def random_movement(self, loop):
        while True:
            if self.stop_now:
                print("STOP?")
                # self.firmware.stop()
                self.stop_now = True
                SigFinish.interrupt_thread(self.random_thread)
                self.random_thread.join()
=======
                self.gb.right_side_turn(run_forever=False, run_by_deg=True,
                                        turn_degree=degree, running_speed=100)
            else:
                self.gb.left_side_turn(run_forever=False, run_by_deg=True,
                                       turn_degree=degree, running_speed=100)

        elif msg == "stop":
            log.info("Stopping.")
            self.gb.stop()
        else:
            log.info("Invalid command.")

>>>>>>> 1e70dfe751db2a5293c571f85c30e0a663f7106f

def socket_sender_establish_loop(client, loop):
    asyncio.set_event_loop(loop)
    client.connect(sender=True)
    loop.run_forever()


def socket_receiver_establish_loop(client, loop):
    asyncio.set_event_loop(loop)
    client.connect(sender=False)
    loop.run_forever()


def main():
    log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s",
                    level=log.INFO, stream=sys.stdout)
    ev3 = EV3_Client()

    ws_receiver = asyncio.new_event_loop()
    ws_receiver_thread = threading.Thread(
        target=socket_receiver_establish_loop, args=(ev3, ws_receiver,))
    ws_receiver_thread.setDaemon(True)
    ws_receiver_thread.start()

    ws_sender = asyncio.new_event_loop()
    ws_sender_thread = threading.Thread(
        target=socket_sender_establish_loop, args=(ev3, ws_sender,))
    ws_sender_thread.setDaemon(True)
    ws_sender_thread.start()

    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    main()
