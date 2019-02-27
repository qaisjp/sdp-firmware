#!/usr/bin/env python3
import config
if config.MOCK:
    import mock as ev3
else:
    import ev3dev.ev3 as ev3
import random
import time
import asyncio
from math import pi
from remote import Remote, RPCType


class GrowBot:
    # Initializer / Instance Attributes
    def __init__(self, battery_level, water_level):
        self.battery_level = battery_level
        self.water_level = water_level

        ## Definitions of all sensors and motors
        self.left_motor = ev3.LargeMotor('outA')
        self.right_motor = ev3.LargeMotor('outB')
        self.arm_motor = ev3.LargeMotor('outC')
        self.front_sensor = ev3.UltrasonicSensor('in1')
        # self.back_sensor = ev3.UltrasonicSensor('in2')

        self.arm_rotation_count = 7 # Number of rotation for the motor to perform to raise/lower the arm
        self.motor_running_speed = 500 # Default running speed to both mobilisation motors
        self.motor_running_time = 1 # Default running time for both mobilisation motors, in seconds
        self.turning_constant = 61 # Constant used for turning around
        self.turning_def_degree = 90 # Default degree used to turn
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
        # if not self.back_sensor.connected:
        #     raise IOError("Plug the back sensor into Port In2.`")

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

    def lower_arm(self, running_speed=None, running_time=None, running_rotations=None):
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

    # Note: time in seconds
    def drive_forward(self, run_forever=True, running_time=None, running_speed=None):
        if not run_forever and running_time is None:
            running_time = self.motor_running_time
        if running_speed is None:
            running_speed = self.motor_running_speed

        if run_forever:
            self.left_motor.run_forever(speed_sp=-int(running_speed))
            self.right_motor.run_forever(speed_sp=-int(running_speed))
        else:
            self.left_motor.run_timed(speed_sp=-int(running_speed), time_sp=running_time * 1000)
            self.right_motor.run_forever(speed_sp=-int(running_speed), time_sp=running_time * 1000)
            time.sleep(running_time)

    def drive_backward(self, run_forever=True, running_time=None, running_speed=None):
        if not run_forever and running_time is None:
            running_time = self.motor_running_time
        if running_speed is None:
            running_speed = self.motor_running_speed

        if run_forever:
            self.left_motor.run_forever(speed_sp=int(running_speed))
            self.right_motor.run_forever(speed_sp=int(running_speed))
        else:
            self.left_motor.run_timed(speed_sp=int(running_speed), time_sp=running_time * 1000)
            self.right_motor.run_forever(speed_sp=int(running_speed), time_sp=running_time * 1000)
            time.sleep(running_time)

    def left_side_turn(self, run_forever=True, run_by_deg=False, run_by_time=False, running_time=None, running_speed=None, turn_degree=None, twin_turn=False):
        # Default parameters
        if running_speed is None:
            running_speed = self.motor_running_speed
        if not run_forever:
            if run_by_deg is True:
                if turn_degree is None:
                    turn_degree = self.turning_def_degree
            elif running_time is None:
                running_time = self.motor_running_time

        if run_forever:
            self.right_motor.run_forever(speed_sp=-int(running_speed))
            if (twin_turn):
                self.left_motor.run_forever(speed_sp=int(running_speed))
            else:
                self.left_motor.stop(stop_action="hold")
        elif run_by_time:
            self.right_motor.run_timed(speed_sp=-int(running_speed), time_sp=int(running_time) * 1000)
            if (twin_turn):
                self.left_motor.run_forever(speed_sp=int(running_speed), time_sp=int(running_time) * 1000)
            else:
                self.left_motor.stop(stop_action="hold")
            time.sleep(running_time)

        else:
            running_dist = -self.turning_constant * int(turn_degree) / 2 / pi
            self.left_motor.stop(stop_action="hold")
            if (turn_degree < 0):
                self.right_motor.run_to_rel_pos(position_sp= -running_dist, speed_sp=running_speed, stop_action="hold")
            else:
                self.right_motor.run_to_rel_pos(position_sp= running_dist, speed_sp=running_speed, stop_action="hold")
            time.sleep(abs(running_dist / running_speed))

    def right_side_turn(self, run_forever=True, run_by_deg=False, run_by_time=False, running_time=None, running_speed=None, turn_degree=None, twin_turn=False):
        # Default parameters
        if running_speed is None:
            running_speed = self.motor_running_speed
        if not run_forever:
            if run_by_deg is True:
                if turn_degree is None:
                    turn_degree = self.turning_def_degree
            elif running_time is None:
                running_time = self.motor_running_time

        if run_forever:
            self.left_motor.run_forever(speed_sp=-int(running_speed))
            if (twin_turn):
                self.right_motor.run_forever(speed_sp=int(running_speed))
            else:
                self.right_motor.stop(stop_action="hold")
        elif run_by_time:
            self.left_motor.run_timed(speed_sp=-int(running_speed), time_sp=int(running_time) * 1000)
            if (twin_turn):
                self.right_motor.run_forever(speed_sp=int(running_speed), time_sp=int(running_time) * 1000)
            else:
                self.right_motor.stop(stop_action="hold")
            time.sleep(running_time)

        else:
            running_dist = -self.turning_constant * int(turn_degree) / 2 / pi
            self.right_motor.stop(stop_action="hold")
            if (turn_degree < 0):
                self.left_motor.run_to_rel_pos(position_sp= -running_dist, speed_sp=running_speed, stop_action="hold")
            else:
                self.left_motor.run_to_rel_pos(position_sp= running_dist, speed_sp=running_speed, stop_action="hold")
            time.sleep(abs(running_dist / running_speed))

    def stop(self, sta="brake"):
        # Stop all the motors
        self.left_motor.stop(stop_action=sta)
        self.right_motor.stop(stop_action=sta)
        self.arm_motor.stop(stop_action=sta)

    def avoidance_routine(self):
        self.drive_backward(run_forever=False, running_time=3)
        self.right_side_turn(run_forever=False, run_by_deg=True, turn_degree=45)
        self.drive_forward(run_forever=False, running_time=2)
        self.left_side_turn(run_forever=False, run_by_deg=True, turn_degree=-45)

    def front_faces_obstacle(self):
        # Returns true if the front sensor returns a value lower than the threshold set
        return (self.front_sensor.value() < self.sensor_threshold)

    def switch_obstacle_detection(self, value):
        self.enable_obstacle_detection = value
    
    def switch_stop_on_obstacle(self, value):
        self.stop_on_obstacle = value

    def remote_move(self, direction):	
        print("Start: moving in direction {}".format(direction))	
        if direction == "forward":	
            self.drive_forward()
        elif direction == "backward":	
            self.drive_backward()	
        elif direction == "left":	
            self.left_side_turn()
        elif direction == "right":	
            self.right_side_turn()	
        elif direction == "brake":	
            self.stop()	
        elif direction == "armup":
            self.raise_arm()
        elif direction == "armdown":
            self.lower_arm()
        else:	
            print("Unknown direction received")	
        print("End: moving in direction {}".format(direction))

def main():
    gb = GrowBot(-1, -1)

    if hasattr(asyncio, 'async'):
        create_task = getattr(asyncio, 'async')
    else:
        create_task = getattr(asyncio, 'ensure_future')

    # Instantiate and use remote
    if config.RESPOND_TO_API:
        host = config.API_HOST
        if config.API_SECURE:
            host = "wss://"+host
        else:
            host = "ws://"+host

        remote = Remote(config.UUID, host)
        remote.add_callback(RPCType.MOVE_IN_DIRECTION, gb.remote_move)
        create_task(remote.connect())

    loop = asyncio.get_event_loop()
    pending = asyncio.Task.all_tasks()
    loop.run_until_complete(asyncio.gather(*pending))

if __name__ == "__main__":
    print("[MAIN] Running!")
    main()
