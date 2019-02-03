#!/usr/bin/env python3
import config
if config.MOCK:
    import mock as ev3
else:
    import ev3dev.ev3 as ev3
import random
import time
import asyncio
from growbot import Remote, RPCType

class GrowBot:
    # Static variables
    ## Steering speeds
    small_steer_speed = 100
    medium_steer_speed = 100
    large_steer_speed = 100

    ## Steer time, in milliseconds
    small_steer_time = 50
    medium_steer_time = 100
    large_steer_time = 150
    
    ## Drive speeds
    forward_speed = 500

    # Initializer / Instance Attributes
    def __init__(self, battery_level, water_level):
        self.battery_level = battery_level
        self.water_level = water_level

        ## Definitions of all sensors and motors
        self.driving_motor = ev3.LargeMotor('outA')
        self.steering_motor = ev3.MediumMotor('outB')
        self.obstacle_sensor = ev3.UltrasonicSensor('in1')

        ## Detect all ports are connected
        ## Expansion: detect types of each port?
        if not (self.driving_motor.connected):
            raise IOError("Plug the large motor into Port A.")
        elif not (self.steering_motor.connected):
            raise IOError("Plug the small motor into Port B.")
        elif not (self.obstacle_sensor.connected):
            raise IOError("Plug the small motor into Port 1.")

    def smallLeft(self):
        # Function will move front wheels left by small amount for ~1sec
        # Precond: driving motor not idle
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = -GrowBot.small_steer_speed, time_sp = GrowBot.small_steer_time)

    def mediumLeft(self):
        # Function will move front wheels left by medium amount for ~1.5sec
        # Precond: driving motor not idle
        (self.driving_motor.is_running)
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = -GrowBot.medium_steer_speed, time_sp = 375)


    def largeLeft(self):
        # Function will move front wheels left by large amount for ~2sec
        # Precond: driving motor not idle
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = -GrowBot.large_steer_speed, time_sp = GrowBot.large_steer_time)

    def smallRight(self):
        # Function will move front wheels right by small amount for ~1sec
        # Precond: driving motor not idle
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = GrowBot.small_steer_speed, time_sp = GrowBot.small_steer_time)
    
    def mediumRight(self):
        # Function will move front wheels right by medium amount for ~1.5sec
        # Precond: driving motor not idle
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = GrowBot.medium_steer_speed, time_sp = 375)

    def largeRight(self):
        # Function will move front wheels right by small amount for ~2sec
        # Precond: driving motor not idle
        if (self.driving_motor.is_running):
            self.steering_motor.run_timed(speed_sp = GrowBot.large_steer_speed, time_sp = GrowBot.large_steer_time)

    def stop(self):
        # Function will set the driving motor to idle
        self.driving_motor.stop(stop_action="brake")

    def forward(self, speed=500):
        # Function will set the driving motor to have +tive speed specified
        # Precond speed > 0
        if (speed <= 0):
            raise (ValueError("Speed must be positive"))
        else:
            self.driving_motor.run_forever(speed_sp = speed)

    def reverse(self, speed=500):
        # Function will set the driving motor to have -tive speed specified
        # Precond speed > 0
        if (speed <= 0):
            raise (ValueError("Speed must be positive"))
        else:
            self.driving_motor.run_forever(speed_sp = -speed)

    def backUp(self):
        # Function call will tell the robot to back up around 1m at a reasonable speed
        return

    # def pumpWater(self, time):
    #     #Function will set the pumpung motor into action for the specified period of time
    #     # precond time>0
    #     return

    # def pumpWater(self):
    #     #Function will set the pumpung motor into action for the set period of time
    #     return

    # PLUS MAY MORE PROBABLY...

    def remote_move(self, direction):
        print("Start: moving in direction {}".format(direction))
        if direction == "forward":
            self.forward()
        elif direction == "backward":
            self.reverse()
        elif direction == "left":
            self.mediumLeft()
            self.forward()
        elif direction == "right":
            remote_wheel_direction = 1
            self.mediumRight()
            self.forward()
        else:
            print("Unknown direction received")
        print("End: moving in direction {}".format(direction))

# Create a main method which makes the robot move around randomly. This will be very useful for training the vision system.
@asyncio.coroutine
def run_forever(growbot):
    while (True):
        if (random.random() < 0.25):
            growbot.stop()
        else:
            drive_rand = random.random()
            steer_rand = random.random()
            intensity_rand = random.random()

            # Driving randomiser
            if (drive_rand < 0.5):
                if (random.random() < 0.8):
                    growbot.forward()
                else:
                    growbot.forward(speed=random.randint(1, 1000))
            else:
                if (random.random() < 0.8):
                    growbot.reverse()
                else:
                    growbot.reverse(speed=random.randint(1,1000))

            # Steering randomiser
            if (steer_rand < 0.5):
                if (intensity_rand < 0.33):
                    growbot.smallLeft()
                elif (intensity_rand < 0.67):
                    growbot.mediumLeft()
                else:
                    growbot.largeLeft()
            else:
                if (intensity_rand < 0.33):
                    growbot.smallRight()
                elif (intensity_rand < 0.67):
                    growbot.mediumRight()
                else:
                    growbot.largeRight()

        # Take a break until the next command
        yield from asyncio.sleep(2)

def main():
    gb = GrowBot(-1, -1)

    # Instantiate and use remote
    host = config.API_HOST
    if config.API_SECURE:
        host = "wss://"+host
    else:
        host = "ws://"+host
    remote = Remote(config.UUID, host)
    remote.add_callback(RPCType.MOVE_IN_DIRECTION, gb.remote_move)

    # Run all tasks
    asyncio.ensure_future(run_forever(gb))
    asyncio.ensure_future(remote.connect())
    pending = asyncio.Task.all_tasks()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(*pending))
    loop.close()

if __name__ == "__main__":
    main()
