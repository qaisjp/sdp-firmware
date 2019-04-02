import serial
import asyncio
import os
import time
import logging as log
import sys

#ser = serial.Serial('/dev/ttyACM0',115200)
#s = [0,1]
#s[0] = str(int(ser.readline()))
#print (s[0])

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
                read = sensor_read.read()
                if read != '':
                    self.sensor_last_read = float(read)
                else:
                    self.sensor_last_read = 0
                sensor_read.close()
        else:
            self.sensor_last_read = 0

    def read_value(self):
        self.value_reading = True
        try:
            value = [0,1]
            value[0] = int(self.ser.readline()) # Attempts to read the sensor
            print(str(value[0]))
            asyncio.set_event_loop(asyncio.new_event_loop())
            self.callback.remote.update_soil_moisture(1, value[0])
            log.info("[SENSOR] Read sensor {} with value {}".format(self.baudrate, str(value[0])))
            # Update time read to now
            with open("sensor_read", mode="w") as sensor_write:
                sensor_write.write(str(time.time()))
                sensor_write.close()
            self.sensor_last_read = time.time()
        except Exception as e:
            log.error("[SENSOR] Sensor value not read due to exception: {}.".format(str(e)))
        finally:
            self.value_reading = False
