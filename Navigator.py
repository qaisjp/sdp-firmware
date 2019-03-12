from RemoteMotorController import RemoteMotorController
import logging as log
import sys
import threading
import asyncio
import time


class Navigator:
    """
    Navigation module for GrowBot robot.
    """

    def sender_action(self, rm, loop):
        asyncio.set_event_loop(loop)
        rm.connect()
        loop.run_forever()

    def receiver_action(self, rm, loop):
        asyncio.set_event_loop(loop)
        rm.connect(sender=False, port_nr=19221)
        loop.run_forever()

    def __init__(self,
                 robot_controller,
                 obstacle_threshold=0.5,
                 plant_approach_threshold=0.50,
                 escape_delay=5,
                 constant_delta=10,
                 verbose=False):
        """
        Constructor for Navigator class.
        :param robot_controller:        RobotController instance coordinating vision and motor control
        :param obstacle_threshold:      Approximate distance metric used to classify obstacles as being close
        :param plant_approach_threshold:         Approximate distance metric used to classify plnts as being close
        :param escape_delay:            Amount of time in seconds to allow robot move away from a plant until following
                                        next one
        :param verbose:                 Verbosity flag
        """
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)

        self.robot_controller = robot_controller
        self.obstacle_threshold = obstacle_threshold
        self.plant_approach_threshold = plant_approach_threshold
        self.escape_delay = escape_delay
        self.constant_delta = constant_delta
        self.verbose = verbose

        self.prediction_dict = {"plants": [], "obstacles": []}

        # Navigator states.
        self.random_search_mode = False
        self.turning_mode = False
        self.follow_mode = False
        self.escape_mode = False
        self.connection_flag = False

        # Frame details.
        self.frame_width = 640
        self.frame_height = 480
        self.frame_midpoint = self.frame_width / 2
        self.frame_area = self.frame_width * self.frame_height

        self.remote_motor_controller = RemoteMotorController(self)
        
        # Establish two websocket connections to new background threads
        ws_sender_loop = asyncio.new_event_loop()
        ws_sender_thread = threading.Thread(target=self.sender_action, args=(self.remote_motor_controller, ws_sender_loop,))
        ws_sender_thread.setDaemon(True)
        ws_sender_thread.start()

        ws_receiver_loop = asyncio.new_event_loop()
        ws_receiver_thread = threading.Thread(target=self.receiver_action, args=(self.remote_motor_controller, ws_receiver_loop,))
        ws_receiver_thread.setDaemon(True)
        ws_receiver_thread.start()

    def change_connection_state(self):
        """
        Changes connection state
        :return:
        """
        self.connection_flag = True
        log.info("Changed connection state.")

    def on_new_frame(self, predictions):
        """
        Acts as an entry point to the class. Each new prediction is transformed here and then processed by the class.
        :param predictions:     Class predictions produced by the VPU
        :return:
        """
        # Avoid acting when websocket is not ready
        if not self.connection_flag:
            return

        # Separate class labels and transform inputs.
        self.prediction_dict["plants"] = [self.process_bb_coordinates(x) for x in predictions if x[0] == "Plant"]
        self.prediction_dict["obstacles"] = [self.process_bb_coordinates(x) for x in predictions if x[0] == "Obstacle"]

        # Sort predictions in descending order based on bounding box to frame midpoint distance.
        self.prediction_dict["plants"].sort(key=lambda tup: abs(self.frame_midpoint - tup[0]))
        self.prediction_dict["obstacles"].sort(key=lambda tup: abs(self.frame_midpoint - tup[0]))

        # Change state given new frame.
        self.change_state_on_new_frame()

    def change_state_on_new_frame(self):
        """
        Changes state of the class after new predictions are received.
        :return:
        """
        if self.prediction_dict["plants"]:
            # Plant detected.

            if self.prediction_dict["plants"]:
                plant = next(iter(self.prediction_dict["plants"]))
            else:
                # Shouldn't really be here but might happen.
                return

            if self.escape_mode:
                # Operating in escape mode. Ignore detection with bb_area greater than threshold.
                if not self.is_plant_approached(plant):
                    self.follow_plant_aux(plant)
            else:
                # Operating in normal mode.
                self.follow_plant_aux(plant)
        else:
            # Plant not detected. Perform random search if not searching already.
            if not self.random_search_mode:
                log.info("Performing random walk...")
                self.random_search_mode = True
                self.remote_motor_controller.random_walk()

    def follow_plant_aux(self, plant):
        """
        Helper function for plant following.
        :param plant:   Plant to be followed.
        :return:
        """
        if self.random_search_mode:
            # Stop random search.
            self.random_search_mode = False
            self.remote_motor_controller.stop()

        if not self.follow_mode:
            # Switch state
            self.follow_mode = True

        self.follow_plant(plant)

    @staticmethod
    def process_bb_coordinates(prediction):
        """
        Applies pre-processing to predictions produced by the VPU
        :param prediction:  Prediction produced by the VPU
        :return:            Tuple containing (bb_midpoint, bb_box_coordinates)
        """
        _, _, ((xmin, ymin), (xmax, ymax)) = prediction

        return xmin + (xmax - xmin) / 2, ((xmin, ymin), (xmax, ymax))

    def follow_plant(self, plant):
        """
        Application logic for plant following procedure.
        :param plant:   Plant to be followed.
        :return:
        """
        log.info("Following a plant...")

        if self.is_centered_plant(plant):
            log.info("Plant found in the centre.")
            # Plant is centered.

            if self.turning_mode:
                # Stop robot from turning.
                log.info("Stopping the robot...")
                self.turning_mode = False
                self.remote_motor_controller.stop()

            if not self.is_plant_approached(plant):
                log.info("Moving forward...")
                # Plant is not in front of the robot.
                self.remote_motor_controller.go_forward()
            else:
                # Plant is in front of the robot. Stop the robot and switch to escape mode.
                log.info("Plant approached.")
                self.escape_mode = True
                self.follow_mode = False
                self.remote_motor_controller.stop()

                # Report to robot controller.
                self.robot_controller.on_plant_found()

                # Start another random walk.
                self.random_search_mode = True
                self.remote_motor_controller.random_walk()

                # Disable escape mode after escape_delay seconds.
                threading.Thread(target=self.disable_escape_mode).start()
        else:
            # Plant isn't centered. Turn right/left.
            log.info("Plant not in the centre.")

            if not self.turning_mode:
                # Robot is not turning. Get side and turn.
                self.turning_mode = True

                # Approximate angle of rotation
                #angle = self.approximate_angle_of_rotation(plant)

                if self.get_bb_midpoint(plant) > self.frame_midpoint:
                    # Turn right
                    log.info("Turning right...")
                    self.remote_motor_controller.turn_right()
                else:
                    # Turn left.
                    log.info("Turning left...")
                    self.remote_motor_controller.turn_left()

    def is_plant_approached(self, plant):
        """
        Checks if plant has been approach by computing bounding box area to frame area.
        :param plant:   Plant seen by the robot
        :return:        True if area ratio is greater than plant_approach_threshold, otherwise false
        """
        return (self.get_bb_area(plant) / self.frame_area) > self.plant_approach_threshold

    def disable_escape_mode(self):
        """
        This function gives the robot time to look around before following next plant.
        :return:
        """
        time.sleep(self.escape_delay)
        self.escape_mode = False
        log.info("Escape mode disabled.")

    def get_bb_area(self, prediction):
        """
        Computes bounding box area.
        :param prediction:  Prediction for which area has to be computed
        :return:            Area of the bounding box
        """
        _, ((xmin, ymin), (xmax, ymax)) = prediction

        return (xmax - xmin) * (ymax - ymin)

    def approximate_angle_of_rotation(self, plant):
        return 0

    def is_centered_plant(self, plant):
        """
        Checks if object is located in the [midpoint-delta, midpoint+delta] interval.
        :param plant:
        :return:
        """
        delta = self.get_dynamic_delta(plant)

        left = self.frame_midpoint - delta
        right = self.frame_midpoint + delta

        bb_midpoint = self.get_bb_midpoint(plant)

        flag = left <= bb_midpoint <= right

        log.info("Left: {0}, Right: {1}, object_midpoint: {2}, Flag: {3}".format(left, right, bb_midpoint, flag))

        return flag

    def get_bb_midpoint(self, prediction):
        """
        Computes bounding box midpoint.
        :param prediction:  Prediction for which area has to be computed
        :return:            Area of the bounding box
        """
        _, ((xmin, _), (xmax, _)) = prediction

        return (xmax + xmin) / 2

    def get_dynamic_delta(self, plant):
        """
        Computes dynamic delta used for convergence procedure. Delta value is computed using
        constant_delta/(bb_width/frame_width) formula
        :param bb_width:    Bounding box width
        :return:            Dynamic delta value
        """
        return self.constant_delta / (self.get_bb_area(plant) / self.frame_area)
