import serial
import asyncio
import os
import time
import logging as log
import sys

class SerialIO:
    def __init__(self, address, baudrate, callback):
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        self.ser = serial.Serial(port=address, baudrate=baudrate, timeout=5)
        self.address = address
        self.baudrate = baudrate
        self.callback = callback
        self.value_reading = False
        if os.path.isfile("sensor_read"):
            with open("sensor_read", mode="r") as sensor_read:
                self.sensor_last_read = int(sensor_read.read())
        else:
            self.sensor_last_read = 0

    @asyncio.coroutine
    def read_value(self):
        self.value_reading = True
        try:
            value = int(self.ser.readline()) # Attempts to read the sensor
            self.callback.remote.update_soil_moisture(1, value)
            log.info("[SENSOR] Read sensor {} with value {}".format(self.baudrate, str(value)))
            # Update time read to now
            with open("sensor_read", mode="w") as sensor_write:
                sensor_write.write(time.time())
        except:
            log.error("[SENSOR] Sensor value not read due to exception.")
        finally:
            self.value_reading = False