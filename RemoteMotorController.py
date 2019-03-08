#!/usr/bin/env python
import logging as log
import sys
import time


class RemoteMotorController:
    def __init__(self):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

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
