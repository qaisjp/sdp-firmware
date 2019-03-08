#!/usr/bin/env python

from RemoteMotorController import RemoteMotorController
import logging as log
import sys
import threading
import time


class Navigator:
    """
    Navigation module for GrowBot robot.
    """

    def __init__(self,
                 robot_controller,
                 obstacle_threshold=0.5,
                 plant_threshold=0.50,
                 escape_delay=10,
                 constant_delta=20,
                 verbose=False):
        """
        Constructor for Navigator class.
        :param robot_controller:        RobotController instance coordinating vision and motor control
        :param obstacle_threshold:      Approximate distance metric used to classify obstacles as being close
        :param plant_threshold:         Approximate distance metric used to classify plnts as being close
        :param escape_delay:            Amount of time in seconds to allow robot move away from a plant until following
                                        next one
        :param verbose:                 Verbosity flag
        """
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

        self.robot_controller = robot_controller
        self.obstacle_threshold = obstacle_threshold
        self.plant_threshold = plant_threshold
        self.escape_delay = escape_delay
        self.verbose = verbose

        self.remote_motor_controller = RemoteMotorController()

        self.frame_width = 1280
        self.frame_height = 720
        self.frame_midpoint = self.frame_width / 2
        self.constant_delta = constant_delta

        # Internal states
        self.follow_mode = False        # Vision system found a plant and robot is moving towards it
        self.escape_mode = False        # Robot just approached a plant and is looking for new ones
        self.avoidance_mode = False     # Vision system found obstacle in front of the robot

        # Search completion flag
        self.search_complete = False  # Set to true if robot visited every node

        # Visual data
        self.prediction_dict = {"plants": [], "obstacles": []}

    def start(self):
        """
        Logic wrapper for GrowBot's random exploration procedure.
        :return:
        """
        # Loop until search is incomplete
        while not self.search_complete:
            if not self.follow_mode:
                # No plant(s) detected. Start looking randomly.
                self.random_search()
            elif self.follow_mode:
                # Plant(s) detected. Start following.
                self.follow_plant()
            elif self.avoidance_mode:
                # Obstacle(s) detected. Start avoiding
                self.avoid_obstacle()

        # Search complete. Return to the base
        self.return_to_base()

    def navigate(self, predictions):
        """
        This function accepts new inputs from the RobotController class. Inputs are separated into plants and obstacles
        and transformed. Transformed inputs are of the form (bb_midpoint, bb_width). Label and probability are dropped.
        After transformation, each object class is sorted in descending order based on bounding box midpoint to frame
        midpoint distance.
        :param predictions: New inputs produced by the VPU
        :return:
        """
        # Separate class labels and transform inputs
        self.prediction_dict["plants"] = [self.process_bb_coordinates(x) for x in predictions if x[0] == "Plant"]
        self.prediction_dict["obstacles"] = [self.process_bb_coordinates(x) for x in predictions if x[0] == "Obstacle"]

        # Sort predictions in descending order based on bounding box to frame midpoint distance
        self.prediction_dict["plants"].sort(key=lambda tup: abs(self.frame_midpoint - tup[0]))
        self.prediction_dict["obstacles"].sort(key=lambda tup: abs(self.frame_midpoint - tup[0]))

        # Change state given new inputs
        self.change_state()

    def return_to_base(self):
        """
        Returns to the base station.
        :return:
        """
        # TODO: Implement return functionality
        pass

    def random_search(self):
        """
        Performs random search until found plant to follow.
        :return:
        """
        # Loop until found plant to follow and escape mode is inactive.
        while not (self.follow_mode or self.escape_mode):
            self.remote_motor_controller.random_walk()

    def follow_plant(self):
        """
        Given that robot discovered new plant(s), this function will first try to move the robot in
        left/right direction until plant is located in [midpoint-delta, midpoint+delta] interval (approximated
        horizontal midpoint). If this condition is satisfied, function will approximate the distance between the robot
        and plant by computing bounding box width to frame width ratio. If ratio is greater than plant_threshold, robot
        starts looking for other plants by performing random walk (escape delay is used to ensure that robot can move
        away from the plant to avoid plant-re-discovery loop), otherwise, robot will move forward. Plant(s)
        are selected based on distance from bounding box midpoint to frame midpoint.
        :return:
        """
        # Loop until plant is located in [midpoint-delta, midpoint+delta] interval
        while not self.check_convergence(next(iter(self.prediction_dict["plants"]))):
            # Turn left/right
            if next(iter(self.prediction_dict["plants"]))[0] >= self.frame_midpoint:
                self.remote_motor_controller.turn_right()
            else:
                self.remote_motor_controller.turn_left()

        # Check if robot is close to a plant, if not then go forward, else change follow_mode flag and perform
        # random walk to find other plants
        if self.approx_distance(next(iter(self.prediction_dict["plants"]))[1]) >= self.plant_threshold:
            if self.verbose:
                log.info("Plant approached.")

            self.follow_mode = False
            self.escape_mode = True

            threading.Thread(target=self.disable_escape_mode).start()

            self.remote_motor_controller.random_walk()
        else:
            if self.verbose:
                log.info("Plant not approached.")
            self.remote_motor_controller.go_forward()

    def avoid_obstacle(self):
        while self.avoidance_mode:
            pass

    def disable_escape_mode(self):
        """
        This function gives the robot time to look around before following next plant.
        :return:
        """
        time.sleep(self.escape_delay)
        self.escape_mode = False
        if self.verbose:
            log.info("Escape mode disabled.")

    def change_state(self):
        """
        Changes internal state given new inputs.
        :return:
        """
        if self.prediction_dict["plants"] and not self.escape_mode:
            # Plant(s) detected. Switch to follow mode
            self.follow_mode = True

            if self.verbose:
                log.info("Changed follow_mode to True.")
        else:
            # No plant(s) detected. Switch to search mode
            self.follow_mode = False

            if self.verbose:
                log.info("Changed follow_mode to False.")

        if self.prediction_dict["obstacles"]:
            # Detect any obstacle(s) in front of the robot
            self.avoidance_mode = any(
                [self.classify_obstacle(obstacle) for obstacle in self.prediction_dict["obstacles"]])

            if self.verbose:
                log.info("Changed avoidance_mode to {}.".format(self.avoidance_mode))

    def check_convergence(self, prediction):
        """
        Checks if object is located in the [midpoint-delta, midpoint+delta] interval.
        :param prediction:  Tuple containing (bb_midpoint, bb_width) of the prediction
        :return:            True if object is located in the [midpoint-delta, midpoint+delta], otherwise false
        """
        delta = self.get_dynamic_delta(prediction[1])

        left = self.frame_midpoint - delta
        right = self.frame_midpoint + delta

        flag = left <= prediction[0] <= right

        if self.verbose:
            log.info("Left: {0}, Right: {1}, object_midpoint: {2}, Flag: {3}".format(left, right, prediction[0], flag))

        return flag

    def approx_distance(self, bb_width):
        """
        Computes bounding box width to frame width ratio to approximate distance between plant and robot.
        :param bb_width:    Bounding box width
        :return:            Bounding box width to frame width ratio
        """
        return bb_width / self.frame_width

    def classify_obstacle(self, obstacle):
        """
        Classifies obstacles into actual obstacles (the ones that are on robot's way) or not.
        :param obstacle:    Obstacle to be classified
        :return:            True if bb_width to frame_width ratio is greater than obstacle_threshold and obstacle is in
                            the centre, otherwise false.
        """
        bb_midpoint, bb_width = obstacle

        return (bb_width / self.frame_width) > self.obstacle_threshold and \
               (bb_midpoint - bb_width / 2) <= self.frame_midpoint <= (bb_midpoint + bb_width / 2)

    @staticmethod
    def process_bb_coordinates(prediction):
        """
        Applies pre-processing to predictions produced by the VPU
        :param prediction:  Prediction produced by the VPU
        :return:            Tuple containing (bb_midpoint, bb_width)
        """
        _, _, ((xmin, _), (xmax, _)) = prediction

        return xmin + (xmax - xmin) / 2, xmax - xmin

    def get_dynamic_delta(self, bb_width):
        """
        Computes dynamic delta used for convergence procedure. Delta value is computed using
        constant_delta/(bb_width/frame_width) formula
        :param bb_width:    Bounding box width
        :return:            Dynamic delta value
        """
        return self.constant_delta / (bb_width / self.frame_width)
