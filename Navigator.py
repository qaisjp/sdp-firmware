from RemoteMotorController import RemoteMotorController
import logging as log
import sys
import threading
import asyncio
import time
import pickle

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
                 plant_approach_threshold=0.5,
                 escape_delay=15,
                 constant_delta=10,
                 verbose=False,
                 approach_frame_timeout=8,
                 random_search_frame_timeout=8):
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
        self.follow_mode = False
        self.escape_mode = False
        self.escape_mode_time = time.time()

        self.random_search_frame_timeout = random_search_frame_timeout
        self.approach_frame_timeout = approach_frame_timeout

        self.random_search_timeout_counter = self.random_search_frame_timeout
        self.approach_frame_counter = self.approach_frame_timeout

        # Frame details.
        self.frame_width = 640
        self.frame_height = 480
        self.frame_midpoint = self.frame_width / 2
        self.frame_area = self.frame_width * self.frame_height

        # Single-frame buffer.
        self.previous_plant_prediction = None

        self.frame_count = None

        self.remote_motor_controller = RemoteMotorController(self.robot_controller)
        self.backing = False

        # Load angle approximation model.
        with open("k2_model.pkl", "rb") as input_file:
            self.angle_model = pickle.load(input_file)

        # Establish two websocket connections to new background threads
        ws_sender_loop = asyncio.new_event_loop()
        ws_sender_thread = threading.Thread(target=self.sender_action, args=(self.remote_motor_controller, ws_sender_loop,))
        ws_sender_thread.setDaemon(True)
        ws_sender_thread.start()

        ws_receiver_loop = asyncio.new_event_loop()
        ws_receiver_thread = threading.Thread(target=self.receiver_action, args=(self.remote_motor_controller, ws_receiver_loop,))
        ws_receiver_thread.setDaemon(True)
        ws_receiver_thread.start()

    def on_new_frame(self, predictions):
        """
        Acts as an entry point to the class. Each new prediction is transformed here and then processed by the class.
        :param predictions:     Class predictions produced by the VPU
        :return:
        """
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

        if not self.robot_controller.approach_complete:
            log.info("\033[0;32m[change_state_on_new_frame] Plant approached, skipping this frame\033[0m")
            return

        if self.robot_controller.retrying_approach:
            log.info("\033[0;33m[change_state_on_new_frame] Retrying approach, skipping this frame\033[0m")
            return

        if self.remote_motor_controller.front_sensor_value is None or self.remote_motor_controller.back_sensor_value is None:
            log.info("\033[0;31m[change_state_on_new_frame] Sensor values contain none, skipping\033[0m")
            return
            # Send stop?

        # Wait n frames until turn is complete
        if self.frame_count is not None:
            if self.frame_count is not 0:
                self.frame_count = self.frame_count - 1
                return

        if self.escape_mode:
            if (time.time() - self.escape_mode_time) >= self.escape_delay:
                self.escape_mode = False
                log.info("[change_state_on_new_frame] Escape mode disabled.")

        if self.prediction_dict["plants"]:
            # Plant detected.

            #if self.plant_discovery_frame_count is not 0:
            #    self.plant_discovery_frame_count = self.plant_discovery_frame_count - 1
            #    return
            #else:
            #    self.plant_discovery_frame_count = 5

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
                self.robot_controller.on_plant_seen()
                self.robot_controller.read_qr_code()
                self.follow_plant_aux(plant)
        else:
            # Plant not detected. Perform random search if not searching already.
            if not self.random_search_mode:
                # TODO: get rid of hardcoded values.

                if self.random_search_timeout_counter is not 0:
                    self.random_search_timeout_counter = self.random_search_timeout_counter - 1
                else:
                    self.random_search_timeout_counter = 8

                    log.info("\033[0;35m[change_state_on_new_frame] Performing random walk...\033[0m")
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
        log.info("\033[0;33m[follow_plant] Following a plant...\033[0m")
        self.robot_controller.read_qr_code()

        if self.is_plant_approached(plant):

            # Count frames to skip.
            if self.approach_frame_counter is not 0:
                self.remote_motor_controller.stop()
                log.info("Potential approach, skipping this frame")
                self.approach_frame_counter = self.approach_frame_counter - 1
                return
            else:
                self.approach_frame_counter = self.approach_frame_timeout

            if self.is_centered_plant(plant):
                self.backing = False
                log.info("\033[0;32m[follow_plant] Plant found in the centre.\033[0m")

                # Plant is in front of the robot. Stop the robot and switch to escape mode.
                log.info("\033[1;37;42m[follow_plant] Plant approached.\033[0m")
                self.enable_escape_mode()
                self.follow_mode = False
                self.remote_motor_controller.stop()

                # Read the QR code and make a decision here
                # self.robot_controller.read_qr_code()
                # If this QR code is the same as the last QR code read, skip this plant to another plant
                # if self.robot_controller.last_qr_approached != self.robot_controller.current_qr_approached and self.robot_controller.current_qr_approached is not None:
                    # log.info("Plant is found and QR is read, continue")
                    # Report to robot controller.
                self.robot_controller.on_plant_found()

                # Start another random walk.
                self.random_search_mode = True
                self.remote_motor_controller.random_walk()

                # Disable escape mode after escape_delay seconds.
                threading.Thread(target=self.disable_escape_mode_threaded, daemon=True).start()
            else:
                log.info("\033[0;33m[follow_plant] Plant not in the centre.\033[0m")
                self.remote_motor_controller.retry_approach()
        else:
            if self.is_centered_plant(plant):
                self.backing = False
                log.info("\033[0;32m[follow_plant] Plant found in the centre.\033[0m")

                print(self.remote_motor_controller.front_sensor_value)
                log.info("\033[0;32m[follow_plant] Moving forward...\033[0m")
                # Plant is not in front of the robot.
                self.remote_motor_controller.go_forward()
            else:
                log.info("\033[0;33m[follow_plant] Plant not in the centre.\033[0m")
                area = self.get_bb_area(plant)
                mdelta = self.get_midpoint_delta(plant)

                #log.info("Area: {0}, MDelta: {1}".format(area,mdelta))

                angle = self.angle_model.predict([[area, mdelta]])[0][0] *.65

                if self.get_bb_midpoint(plant) > self.frame_midpoint:
                    # Turn right
                    log.info("\033[0;33m[follow_plant] Turning right by {} degrees...\033[0m".format(angle))
                    self.remote_motor_controller.turn_right(angle)
                else:
                    # Turn left.
                    log.info("\033[0;33m[follow_plant] Turning left by {} degrees...\033[0m".format(angle))
                    self.remote_motor_controller.turn_left(angle)

                self.frame_count = 10

    def disable_escape_mode_threaded(self):
        time.sleep(self.escape_delay)
        self.escape_mode = False
        log.info("Escape mode disabled.")

    def enable_escape_mode(self):
        self.escape_mode_time = time.time()
        self.escape_mode = True
        log.info("Escape mode enabled.")

    def is_plant_approached(self, plant):
        """
        Checks if plant has been approach by computing bounding box area to frame area.
        :param plant:   Plant seen by the robot
        :return:        True if area ratio is greater than plant_approach_threshold, otherwise false
        """
        sensor_flag = False
        sensor_sum = 0
        sensor_count = 0
        
        for i in self.remote_motor_controller.front_sensor_value:
            if i <= 2000:
                sensor_count += 1
                sensor_sum += i
        
        if sensor_count > 0 and sensor_sum / sensor_count < 600:
            sensor_flag = True

        vision_flag = (self.get_bb_area(plant) / self.frame_area) > self.plant_approach_threshold

        return sensor_flag or vision_flag

    def get_bb_area(self, prediction):
        """
        Computes bounding box area.
        :param prediction:  Prediction for which area has to be computed
        :return:            Area of the bounding box
        """
        _, ((xmin, ymin), (xmax, ymax)) = prediction

        return (xmax - xmin) * (ymax - ymin)

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

        #log.info("Left: {0}, Right: {1}, object_midpoint: {2}, Flag: {3}".format(left, right, bb_midpoint, flag))

        return flag

    def get_bb_midpoint(self, prediction):
        """
        Computes bounding box midpoint.
        :param prediction:  Prediction for which area has to be computed
        :return:            Area of the bounding box
        """
        _, ((xmin, _), (xmax, _)) = prediction

        return (xmax + xmin) / 2

    def get_midpoint_delta(self, prediction):
        """
        Computes horizontal distance between bounding box and frame centre.
        :param prediction:  Prediction for horizontaldistance has to be computed
        :return:            Horizontal distance between bb and frame centre.
        """
        return abs(self.frame_midpoint - self.get_bb_midpoint(prediction))

    def get_dynamic_delta(self, plant):
        """
        Computes dynamic delta used for convergence procedure. Delta value is computed using
        constant_delta/(bb_width/frame_width) formula
        :param bb_width:    Bounding box width
        :return:            Dynamic delta value
        """
        return self.constant_delta / (self.get_bb_area(plant) / self.frame_area)

    def remote_move(self, direction):
        if direction == "forward":
            self.remote_motor_controller.go_forward()
        elif direction == "backward":
            self.remote_motor_controller.go_backward()
        elif direction == "left":
            self.remote_motor_controller.turn_left(-1)
        elif direction == "right":
            self.remote_motor_controller.turn_right(-1)
        elif direction == "brake":
            self.remote_motor_controller.stop()
        elif direction == "armup":
            print('armup')
        elif direction == "armdown":
            print('armdown')
        else:
            print("Unknown direction received")
