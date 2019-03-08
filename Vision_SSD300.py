#!/usr/bin/env python
import cv2
import time
import logging as log
import sys
import math
import base64
import threading

from openvino.inference_engine import IENetwork, IEPlugin
from websocket import create_connection
from imutils.video import FPS


class Vision:
    def __init__(self, model_xml, model_bin, robot_controller, is_headless, live_stream, confidence_interval):
        """
        Vision class constructor.
        :param model_xml:           Network topology
        :param model_bin:           Network weights
        :param is_headless:         Headless mode flag, if set to true, frames will not be displayed
        :param live_stream:         Live streaming flag, if set to true, frames will be send through websocket
        :param confidence_interval: Confidence interval for predictions. Only predictions above this value will be
                                    processed
        """
        log.basicConfig(format="[ %(asctime)s ] [ %(levelname)s ] %(message)s", level=log.INFO, stream=sys.stdout)
        log.info("Instantiating Vision class...")

        # Websocket endpoint for live streaming
        ws_endpoint = "ws://api.growbot.tardis.ed.ac.uk/stream-video/35ae6830-d961-4a9c-937f-8aa5bc61d6a3"

        self.is_headless = is_headless
        self.confidence_interval = confidence_interval
        self.live_stream = live_stream
        self.robot_controller = robot_controller

        # Initialize plugin
        log.info("Initializing plugin for MYRIAD X VPU...")
        self.plugin = IEPlugin(device='MYRIAD')

        # Initialize network
        log.info("Reading Intermediate Representation...")
        self.net = IENetwork(model=model_xml, weights=model_bin)

        # Initialize IO blobs
        self.input_blob = next(iter(self.net.inputs))
        self.out_blob = next(iter(self.net.outputs))

        # Load network into IE plugin
        log.info("Loading Intermediate Representation to the plugin...")
        self.exec_net = self.plugin.load(network=self.net, num_requests=2)

        # Extract network's input layer information
        self.n, self.c, self.h, self.w = self.net.inputs[self.input_blob].shape

        # Initialize VideoCapture and let it warm up
        self.cap = cv2.VideoCapture(0)
        time.sleep(1)

        # Initialize FPS counter
        self.fps = FPS()

        # Get capture dimensions
        self.initial_w = self.cap.get(3)
        self.initial_h = self.cap.get(4)

        # Used to provide OpenCV rendering time
        self.render_time = 0

        # Initialize websocket
        if self.live_stream:
            log.info("Connecting to websocket...")
            self.ws = create_connection(ws_endpoint)

    def start(self):
        """
        Starts video capture and performs inference using MYRIAD X VPU
        :return:
        """
        self.fps.start()

        log.info("Starting video stream. Press ESC to stop.")

        ret, frame = self.cap.read()

        # Async request identifiers
        cur_request_id = 0
        next_request_id = 1

        while self.cap.isOpened():
            try:
                self.fps.update()

                # Read next frame
                ret, next_frame = self.cap.read()

                # Break if failed to read
                if not ret:
                    break

                # Main synchronization point. Start the next inference request,
                # while waiting for the current one to complete.
                inf_start = time.time()

                # Resize, change layout, reshape to fit network input size and start asynchronous inference
                in_frame = cv2.resize(next_frame, (self.w, self.h))
                in_frame = in_frame.transpose((2, 0, 1))  # Change data layout from HWC to CHW
                in_frame = in_frame.reshape((self.n, self.c, self.h, self.w))
                self.exec_net.start_async(request_id=next_request_id, inputs={self.input_blob: in_frame})

                if self.exec_net.requests[cur_request_id].wait(-1) == 0:
                    # Capture inference time
                    inf_end = time.time()
                    det_time = inf_end - inf_start

                # Parse detection results of the current request
                res = self.exec_net.requests[cur_request_id].outputs[self.out_blob]

                predictions = [self.process_prediction(frame, pred) for pred in res[0][0] if self.check_threshold(pred[2])]
                self.robot_controller.process_visual_data(predictions)

                # Display frame
                self.process_frame(frame)
                # TODO: Fix live stream
                #threading.Thread(target=self.process_frame, args=(frame,)).start()

                # Swap async request identifiers
                cur_request_id, next_request_id = next_request_id, cur_request_id
                frame = next_frame

                # Enable key detection in output window
                key = cv2.waitKey(1)

                # Check if ESC has been pressed
                if key == 27:
                    self.cleanup()
                    break

            # Catch ctrl+c while in headless mode
            except KeyboardInterrupt:
                self.cleanup()
                break

    def process_frame(self, frame):
        """
        Based on constructor parameters, displays and/or sends frame through websocket.
        :param frame:   Frame to be processed
        :return:
        """
        # Send frame if specified
        if self.live_stream:
            log.info("Sending frame...")
            self.ws.send(base64.b64encode(cv2.imencode(".jpg", frame)[1]))

        # Display frame if specified
        if not self.is_headless:
            render_start = time.time()

            cv2.imshow("Detection Results", frame)

            render_end = time.time()
            self.render_time = render_end - render_start

    @staticmethod
    def visualise_prediction(frame, pred_boxpts, label, prob):
        """
        Draws bounding box and class probability around prediction.
        :param frame:       Frame that contains prediction
        :param pred_boxpts: Bounding box coordinates
        :param label:       Class label
        :param prob:        Class probability
        :return:
        """
        # Draw bounding box and class label
        color = (0, 255, 0) if label == "Plant" else (0, 0, 255)
        cv2.rectangle(frame, pred_boxpts[0], pred_boxpts[1], color, 2)
        cv2.putText(frame,
                    label + ' ' + str(round(prob * 100, 1)) + ' %',
                    (pred_boxpts[0][0], pred_boxpts[0][1] - 7),
                    cv2.FONT_HERSHEY_COMPLEX,
                    0.5,
                    color,
                    1)

    def process_prediction(self, frame, prediction):
        """
        Helper function responsible for bounding box extraction, labelling and data visualization.
        :param frame:       Frame that contains prediction
        :param prediction:  Actual prediction produced by the VPU
        :return:            Triple that contains class label, class probability and prediction bounding boxes
        """
        # Extract bounding box coordinates in the format (xmin, ymin), (xmax, ymax)
        pred_boxpts = ((int(prediction[3] * self.initial_w),
                        int(prediction[4] * self.initial_h)),
                       (int(prediction[5] * self.initial_w),
                        int(prediction[6] * self.initial_h)))

        # Set class label
        label = 'Plant' if int(prediction[1]) == 16 else 'Obstacle'

        log.info("Prediction: {0}, confidence={1:.10f}, boxpoints={2}".format(label,
                                                                              round(prediction[2], 4),
                                                                              pred_boxpts))

        # Draw bounding box and class label with its probability
        self.visualise_prediction(frame, pred_boxpts, label, prediction[2])

        return label, prediction[2], pred_boxpts

    def check_threshold(self, probability):
        """
        Validate and check probability of a prediction.
        :param probability: Class probability
        :return:            True if probability is not NaN and is within (confidence_interval,1]
        """
        return (not math.isnan(probability)) and 1 >= probability > self.confidence_interval

    def cleanup(self):
        """
        Performs cleanup before termination.
        :return:
        """
        self.cap.release()

        if self.live_stream:
            self.ws.close()

        if not self.is_headless:
            cv2.destroyAllWindows()

        self.fps.stop()
