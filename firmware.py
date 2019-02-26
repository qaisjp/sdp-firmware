#!/usr/bin/env python3
import config
if config.MOCK:
    import mock as ev3
else:
    import ev3dev.ev3 as ev3
import random
import time
import asyncio

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

    ## Obstacle detection threshold (in mm)
    obstacle_threshold = 170
    obstacle_counter = 0

    # Initializer / Instance Attributes
    def __init__(self, battery_level, water_level):
        self.battery_level = battery_level
        self.water_level = water_level

        ## Definitions of all sensors and motors
        self.left_motor = ev3.LargeMotor('outA')
        self.right_motor = ev3.LargeMotor('outB')
        self.arm_motor = ev3.LargeMotor('outC')
        self.front_sensor = ev3.UltrasonicSensor('in1')
        self.back_sensor = ev3.UltrasonicSensor('in2')

        self.arm_rotation_count = 7 # Number of rotation for the motor to perform to raise/lower the arm
        self.motor_running_speed = 500 # Default running speed to both mobilisation motors
        self.motor_running_time = 1 # Default running time for both mobilisation motors, in seconds
        self.turning_constant = 61 # Constant used for turning around
        self.sensor_threshold = 40 # Distance used by front/back sensor to stop the robot beyond this value, in cm

        ## Defines robot behaviours
        self.enable_obstacle_detection = False
        self.stop_on_obstacle = True

        ## Detect all ports are connected
        ## Expansion: detect types of each port?
        if not self.left_motor.connected:
            raise IOError("Plug the left motor into Port OutA.")
        if not self.right_motor.connected:
            raise IOError("Plug the right motor into Port OutB.")
        if not self.arm_motor.connected:
            raise IOError("Plug the arm motor into Port OutC.")
        if not self.front_sensor.connected:
            raise IOError("Plug the front sensor into Port In1.")
        if not self.back_sensor.connected:
            raise IOError("Plug the back sensor into Port In2.`")

    def raise_arm(self, running_speed=None, running_time=None, running_rotations=None):
        # Using default params
        if running_speed is None:
            running_speed = self.motor_running_speed
        if running_time is None:
            running_time = self.motor_running_time
        if running_rotations is None:
            running_rotations = self.arm_rotation_count
        
        running_count = -self.arm_motor.count_per_rot * self.arm_rotation_count # Tacho counts for the requested rotations
        # Run to targeted position, and sleep for the duration of the manouvure to avoid command overlap
        self.arm_motor.run_to_rel_pos(position_sp=running_count, speed_sp=running_speed, stop_action="hold")
        time.sleep(abs(running_count / running_speed))

    def lowers_arm(self, running_speed=None, running_time=None, running_rotations=None):
        # Using default params
        if running_speed is None:
            running_speed = self.motor_running_speed
        if running_time is None:
            running_time = self.motor_running_time
        if running_rotations is None:
            running_rotations = self.arm_rotation_count
        
        running_count = self.arm_motor.count_per_rot * self.arm_rotation_count # Tacho counts for the requested rotations
        # Run to targeted position, and sleep for the duration of the manouvure to avoid command overlap
        self.arm_motor.run_to_rel_pos(position_sp=running_count, speed_sp=running_speed, stop_action="hold")
        time.sleep(abs(running_count / running_speed))

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
            if self.enable_obstacle_detection and self.faces_obstacle():
                if self.stop_on_obstacle:
                    self.stop()
                else:
                    self.demo_avoidance_retreat()
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

    def faces_obstacle(self):
        # Returns true if the obstacle sensor returns a value lower than the threshold set
        return (self.obstacle_sensor.value() < self.obstacle_threshold)

    def switch_obstacle_detection(self, value):
        self.enable_obstacle_detection = value
    
    def switch_stop_on_obstacle(self, value):
        self.stop_on_obstacle = value

    ### Migrated from demo_avoidance.py

    # Show obstacle avoidance of the robot - Make the robot run a straight line
    # path through the room, but with various obstacles in the way. The robot
    # should use its IR sensor to detect the object in its path, stop, and navigate
    # around the object.
    def demo_avoidance_retreat(self):
        self.reverse_timed(time = 4000)
        yield from asyncio.sleep(4)
        
        if(self.obstacle_counter % 2 > 0):
            self.rightTurn(time = 450)
            self.forward()
            yield from asyncio.sleep(1)
            self.leftTurn(time=450)
        else:
            self.leftTurn(time = 450)
            self.forward()
            yield from asyncio.sleep(1)
            self.rightTurn(time=450)
        
        self.obstacle_counter += 1

    def leftTurn(self, time = 375):
        self.steering_motor.run_timed(speed_sp = -GrowBot.medium_steer_speed, time_sp = time)

    def rightTurn(self,time = 375):
        self.steering_motor.run_timed(speed_sp = GrowBot.medium_steer_speed, time_sp = time)

    def reverse_timed(self,speed = 300,time = 2000):
        if (speed <= 0):
            raise (ValueError("Speed must be positive"))
        else:
            self.driving_motor.run_timed(speed_sp = -speed, time_sp = time)

    ### End section

    # def pumpWater(self, time):
    #     #Function will set the pumpung motor into action for the specified period of time
    #     # precond time>0
    #     return

    # def pumpWater(self):
    #     #Function will set the pumpung motor into action for the set period of time
    #     return

    # PLUS MAY MORE PROBABLY...


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
    grow_bot_inst = GrowBot(-1, -1) # No parameters yet
    # asyncio.run(run_forever(grow_bot_inst)) # Introduced in 3.7
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_forever(grow_bot_inst))
    loop.close()

if __name__ == "__main__":
    main()
